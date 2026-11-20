"""Single-process authoring gateway. Tokens are assigned to a project by the operator."""
import asyncio
from collections import OrderedDict
from contextlib import asynccontextmanager
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Literal

import httpx
from fastapi import FastAPI, Header, HTTPException
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import BaseModel, Field

PROMPT = ("Read a designer's three-line wireframe from top to bottom. "
          "Translate each line into its matching component ID. Keep their order. "
          "Return only a JSON object with a rows array.")
ROW_PROMPT = ("Which component implements this UI description? Match its meaning to one ID from "
              "the supplied catalogue. Return the ID of the best match in the component field.")
CACHE_LIMIT = 128


class Draft(BaseModel):
    wireframe: str = Field(min_length=3, max_length=800)
    model: Literal["qwen", "smol"] = "qwen"


@asynccontextmanager
async def lifespan(app):
    tokens = json.loads(os.environ["HUD_TOKENS"])
    if not tokens or any(not key or project not in {"atlas", "freight", "soccer"}
                         for key, project in tokens.items()):
        raise ValueError("Configure HUD_TOKENS as a token-to-project JSON object")
    endpoints = {name: os.environ.get(f"HUD_{name.upper()}_URL") for name in ("smol", "qwen")}
    params = StdioServerParameters(command=sys.executable, args=[str(Path(__file__).with_name("contracts.py"))])
    async with stdio_client(params) as (reader, writer), ClientSession(reader, writer) as mcp:
        await mcp.initialize()
        catalogues = {}
        for project in set(tokens.values()):
            resource = await mcp.read_resource(f"hud://catalogue/{project}")
            catalogues[project] = json.loads(resource.contents[0].text)
        async with httpx.AsyncClient(timeout=40) as client:
            app.state.gateway = Gateway(tokens, endpoints, catalogues, mcp, client)
            try:
                yield
            finally:
                await asyncio.gather(*app.state.gateway.pending.values(), return_exceptions=True)


class Gateway:
    def __init__(self, tokens, endpoints, catalogues, mcp, client):
        self.strategy = os.environ.get("HUD_STRATEGY", "whole")
        if self.strategy not in {"whole", "per_row"}:
            raise ValueError("HUD_STRATEGY must be whole or per_row")
        self.tokens = tokens
        self.endpoints = endpoints
        self.catalogues = catalogues
        self.mcp = mcp
        self.client = client
        self.cache = OrderedDict()
        self.pending = {}
        self.slots = asyncio.Semaphore(4)

    async def complete(self, model, system_prompt, context, schema):
        payload = {"model": model, "temperature": 0, "seed": 42, "max_tokens": 80,
                   "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": context}],
                   "response_format": {"type": "json_schema", "json_schema": {"name": "hud", "schema": schema}}}
        async with self.slots:
            response = await self.client.post(self.endpoints[model].rstrip("/") + "/v1/chat/completions", json=payload)
        response.raise_for_status()
        body = response.json()
        return json.loads(body["choices"][0]["message"]["content"]), body["usage"]["total_tokens"]

    async def generate(self, project, draft, catalogue):
        component = {"type": "string", "enum": sorted(catalogue)}
        context = "Components: " + json.dumps(catalogue)
        try:
            if self.strategy == "whole":
                schema = {"type": "object", "properties": {"rows": {"type": "array", "minItems": len(catalogue),
                          "maxItems": len(catalogue), "items": component}}, "required": ["rows"], "additionalProperties": False}
                obj, tokens = await self.complete(draft.model, PROMPT, context + "\nWireframe:\n" + draft.wireframe, schema)
                rows = obj["rows"]
            else:
                lines = [line.strip() for line in draft.wireframe.splitlines() if line.strip()]
                if len(lines) != len(catalogue):
                    raise HTTPException(422, "Use one wireframe line per component")
                schema = {"type": "object", "properties": {"component": component}, "required": ["component"],
                          "additionalProperties": False}
                answers = await asyncio.gather(*(self.complete(draft.model, ROW_PROMPT,
                    context + "\nDescription: " + line, schema) for line in lines))
                rows = [obj["component"] for obj, _ in answers]
                tokens = sum(count for _, count in answers)
            verdict = await self.mcp.call_tool("check_rows", {"project": project, "rows": rows})
            if verdict.isError or not verdict.structuredContent["valid"]:
                raise HTTPException(422, {"message": "Model draft failed the component contract",
                                          "raw_rows": rows, "inference_tokens": tokens})
            return {"rows": rows, "inference_tokens": tokens}
        except (httpx.HTTPError, KeyError, ValueError, TypeError, IndexError) as problem:
            raise HTTPException(502, "Model endpoint returned an unusable response") from problem

    async def run(self, token, draft):
        project = self.tokens.get(token)
        if not project:
            raise HTTPException(401, "Unknown project credential")
        if not self.endpoints[draft.model]:
            raise HTTPException(503, "Model endpoint is not configured")
        catalogue = self.catalogues[project]
        key = hashlib.sha256(json.dumps([project, draft.model, self.strategy, PROMPT, ROW_PROMPT, catalogue, draft.wireframe],
                                        sort_keys=True).encode()).digest()
        if key in self.cache:
            self.cache.move_to_end(key)
            return {"rows": self.cache[key], "cache": "hit", "inference_tokens": 0}
        status = "joined"
        if key not in self.pending:
            if len(self.pending) >= 16:
                raise HTTPException(429, "Draft queue full")
            async def compute():
                try:
                    value = await asyncio.wait_for(self.generate(project, draft, catalogue), timeout=110)
                    self.cache[key] = value["rows"]
                    if len(self.cache) > CACHE_LIMIT:
                        self.cache.popitem(last=False)
                    return value
                except asyncio.TimeoutError as error:
                    raise HTTPException(504, "Draft deadline elapsed") from error
                finally:
                    self.pending.pop(key, None)
            self.pending[key] = asyncio.create_task(compute())
            status = "miss"
        value = await asyncio.shield(self.pending[key])
        return {"rows": value["rows"], "cache": status,
                "inference_tokens": value["inference_tokens"] if status == "miss" else 0}


app = FastAPI(lifespan=lifespan)


@app.post("/draft")
async def draft_layout(draft: Draft, authorization: str = Header(default="")):
    started = time.perf_counter()
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Use a project credential")
    result = await app.state.gateway.run(authorization[7:], draft)
    return {**result, "strategy": app.state.gateway.strategy, "model": draft.model, "latency_ms": round((time.perf_counter() - started) * 1000, 1)}
