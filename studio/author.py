"""Run the two local authoring routes and record candidates and solver decisions."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import time
import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main(output):
    params = StdioServerParameters(command=sys.executable, args=[str(Path(__file__).with_name("chart_mcp.py"))],
                                   env={"ATLAS_ORACLE": os.environ["ATLAS_ORACLE"]})
    async with stdio_client(params) as (r, w), ClientSession(r, w) as session, httpx.AsyncClient(timeout=90) as client:
        await session.initialize()
        brief = json.loads((await session.read_resource("atlas://design/nightwatch")).contents[0].text)
        schema = {"type": "object", "properties": {"pair": {"type": "string", "enum": list(brief["relay_pairs"])},
                  "route": {"type": "string", "enum": list(brief["routes"])}, "title": {"type": "string"}},
                  "required": ["pair", "route", "title"], "additionalProperties": False}
        trials = []
        for model in ("qwen", "smol"):
            prompt = json.dumps(brief)
            for attempt in range(2):
                start = time.perf_counter()
                request = {"model": model, "seed": 42, "temperature": 0, "max_tokens": 120,
                           "messages": [{"role": "user", "content": prompt}],
                           "response_format": {"type": "json_schema", "json_schema": {"name": "chart", "schema": schema}}}
                response = await client.post(os.environ[f"HUD_{model.upper()}_URL"] + "/v1/chat/completions", json=request)
                response.raise_for_status()
                body = response.json()
                proposal = json.loads(body["choices"][0]["message"]["content"])
                checked = await session.call_tool("review_chart", {k: proposal[k] for k in ("pair", "route")})
                if checked.isError:
                    raise RuntimeError(checked.content)
                verdict = checked.structuredContent
                trials.append({"model": model, "attempt": attempt + 1, "proposal": proposal, "review": verdict,
                               "tokens": body["usage"]["total_tokens"], "elapsed_ms": round(1000*(time.perf_counter()-start))})
                if verdict["accepted"]:
                    break
                prompt += "\nRejected proposal: " + json.dumps(proposal) + ". Solver result: " + json.dumps(verdict) + ". Choose another route and pair."
        fixture = await session.call_tool("review_chart", {"pair": "horizon", "route": "shoal"})
        assert not fixture.structuredContent["accepted"]
        with output.open("x") as f:
            json.dump({"context": brief, "candidates": trials, "negative_control": fixture.structuredContent}, f, indent=2)
        print([(t["proposal"], t["review"]) for t in trials])


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--output", type=Path, required=True)
    asyncio.run(main(cli.parse_args().output))
