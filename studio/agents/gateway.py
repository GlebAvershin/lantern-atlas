"""Project-scoped reviewer. Replicas coordinate accepted decisions in PostgreSQL."""
import asyncio
from contextlib import asynccontextmanager
import hashlib
import hmac
import json
import os
import sys

import httpx
import psycopg
from psycopg.types.json import Jsonb
from fastapi import FastAPI, Header, HTTPException
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import BaseModel, Field
from typing import Literal

PROMPT = "Review the supplied game design brief. Select the best available option and return its ID as choice."
MODELS = {
    "qwen": ("QWEN_URL", "Qwen2.5-0.5B:74a4da8c9fdbcd15"),
    "smol": ("SMOL_URL", "SmolLM2-360M:48ab3034d0dd401f"),
}


async def database():
    return await psycopg.AsyncConnection.connect(os.environ["STUDIO_DB"], connect_timeout=5)


@asynccontextmanager
async def lifespan(app):
    params = StdioServerParameters(command=os.environ.get("TOOL_PYTHON", sys.executable),
        args=[os.environ["REVIEW_SERVER"]], env={"ATLAS_ORACLE": os.environ.get("ATLAS_ORACLE", "")})
    async with stdio_client(params) as (reader, writer), ClientSession(reader, writer) as mcp:
        await mcp.initialize()
        resource = await mcp.read_resource("studio://review/brief")
        brief = json.loads(resource.contents[0].text)
        if len(json.dumps(brief).encode()) > 8192 or not 1 <= len(brief["options"]) <= 4:
            raise ValueError("Brief exceeds the release review budget")
        async with await database() as db:
            # Serialize first boot of multiple replicas, including table creation.
            await db.execute("SELECT pg_advisory_xact_lock(117433, 1)")
            await db.execute("""CREATE TABLE IF NOT EXISTS review_cache (
                cache_key text PRIMARY KEY, result jsonb NOT NULL, expires_at timestamptz NOT NULL)""")
            await db.execute("DELETE FROM review_cache WHERE expires_at <= now()")
        async with httpx.AsyncClient(timeout=30) as client:
            app.state.mcp, app.state.brief, app.state.client = mcp, brief, client
            app.state.tokens = json.loads(os.environ["STUDIO_TOKENS"])
            if not app.state.tokens or any(not key or not value for key, value in app.state.tokens.items()):
                raise ValueError("Missing tenant credentials")
            control = await mcp.read_resource("studio://review/negative-control")
            choice = control.contents[0].text
            verdict = await verify(choice)
            if choice not in brief["options"] or verdict["accepted"]:
                raise ValueError("The game verifier must reject the negative control")
            app.state.control = {"choice": choice, "verdict": verdict}
            app.state.slots = asyncio.Semaphore(12)
            yield


app = FastAPI(lifespan=lifespan)


class Request(BaseModel):
    model: Literal["qwen", "smol"]
    allow_fallback: bool = True
    candidates: list[str] | None = Field(default=None, min_length=1, max_length=4)


async def verify(choice):
    result = await app.state.mcp.call_tool("verify_choice", {"choice": choice})
    if result.isError or not isinstance(result.structuredContent, dict):
        raise HTTPException(502, "Game verifier failed")
    return result.structuredContent


class ModelUnavailable(Exception):
    """The inference transport failed before a usable response was received."""


async def generate(model, brief):
    remaining = dict(brief["options"])
    history = []
    tokens = 0
    while remaining:
        schema = {"type": "object", "properties": {"choice": {"type": "string", "enum": list(remaining)}},
                  "required": ["choice"], "additionalProperties": False}
        context = json.dumps({**brief, "options": remaining, "previous_reviews": history}, sort_keys=True)
        try:
            response = await app.state.client.post(os.environ[MODELS[model][0]] + "/v1/chat/completions",
                json={"model": model, "temperature": 0, "seed": 42, "max_tokens": 48,
                      "messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": context}],
                      "response_format": {"type": "json_schema", "json_schema": {"name": "decision", "schema": schema}}})
            response.raise_for_status()
        except httpx.TransportError as error:
            raise ModelUnavailable(model) from error
        except httpx.HTTPStatusError as error:
            if error.response.status_code in (408, 429) or error.response.status_code >= 500:
                raise ModelUnavailable(model) from error
            raise
        completion = response.json()
        tokens += completion["usage"]["total_tokens"]
        choice = json.loads(completion["choices"][0]["message"]["content"])["choice"]
        if choice not in remaining:
            raise HTTPException(502, "Model returned an unknown choice")
        verdict = await verify(choice)
        history.append({"choice": choice, "verdict": verdict})
        if verdict["accepted"]:
            return {"choice": choice, "history": history, "tokens": tokens}
        del remaining[choice]
    raise HTTPException(422, "Game verifier rejected every candidate")


@app.get("/ready")
async def ready():
    return {"project": os.environ["STUDIO_PROJECT"], "negative_control": app.state.control}


async def cached_review(team, model, brief):
    identity = [os.environ["STUDIO_PROJECT"], team, model, MODELS[model][1], os.environ["RELEASE_REVISION"],
                os.environ["PLATFORM_REVISION"], PROMPT, brief]
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    lock_id = int.from_bytes(bytes.fromhex(key)[:8], "big", signed=True)
    async with await database() as db:
        # With READ COMMITTED the select after the lock sees the winning transaction.
        await db.execute("SELECT pg_advisory_xact_lock(%s)", (lock_id,))
        cur = await db.execute("SELECT result FROM review_cache WHERE cache_key=%s AND expires_at > now()", (key,))
        row = await cur.fetchone()
        if row:
            return {"result": row[0], "cache": "hit", "inference_tokens": 0}
        result = await generate(model, brief)
        await db.execute("""INSERT INTO review_cache VALUES (%s,%s, now() + interval '1 day')
            ON CONFLICT (cache_key) DO UPDATE SET result=EXCLUDED.result, expires_at=EXCLUDED.expires_at""",
            (key, Jsonb(result)))
        return {"result": result, "cache": "miss", "inference_tokens": result["tokens"]}


@app.post("/review")
async def review(request: Request, authorization: str = Header(default="")):
    team = next((value for token, value in app.state.tokens.items() if
                 hmac.compare_digest(authorization.encode(), ("Bearer " + token).encode())), None)
    if team is None:
        raise HTTPException(401, "Unknown team credential")
    brief = app.state.brief
    if request.candidates is not None:
        options = brief["options"]
        selected = set(request.candidates)
        if len(selected) != len(request.candidates) or not selected.issubset(options):
            raise HTTPException(422, "Select distinct choices from the game catalogue")
        brief = {**brief, "options": {key: value for key, value in options.items() if key in selected}}
    try:
        async with asyncio.timeout(90), app.state.slots:
            model = request.model
            try:
                result = await cached_review(team, model, brief)
            except ModelUnavailable:
                if not request.allow_fallback:
                    raise HTTPException(502, "Requested model unavailable")
                model = "smol" if model == "qwen" else "qwen"
                try:
                    result = await cached_review(team, model, brief)
                except ModelUnavailable as error:
                    raise HTTPException(503, "Both model routes unavailable", headers={"Retry-After": "5"}) from error
    except TimeoutError as error:
        raise HTTPException(504, "Review deadline exceeded") from error
    except (httpx.HTTPError, ValueError, KeyError, IndexError, psycopg.Error) as error:
        raise HTTPException(502, "Review dependency failed") from error
    return {**result, "model": model, "requested_model": request.model, "fallback": model != request.model, "worker": os.environ["HOSTNAME"]}
