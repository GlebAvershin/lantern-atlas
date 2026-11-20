"""A bounded, read-only GitHub MCP review feeding a model a real PR's persistence context."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.request import Request, urlopen
import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.server.fastmcp import FastMCP

server = FastMCP("Atlas PR review")
REPO = "GlebAvershin/lantern-atlas"


def read_public(url):
    with urlopen(Request(url, headers={"User-Agent": "lantern-atlas-release-review"}), timeout=20) as response:
        return response.read(200000).decode()


@server.resource("atlas://github/nightwatch/persistence")
def context() -> dict:
    """Read the head of the Nightwatch PR and only the file implementing saved state."""
    pr = json.loads(read_public(f"https://api.github.com/repos/{REPO}/pulls/1"))
    sha = pr["head"]["sha"]
    source = read_public(f"https://raw.githubusercontent.com/{REPO}/{sha}/game/logbook.gd")
    return {"pr": pr["html_url"], "sha": sha, "file": "game/logbook.gd",
            "sha256": hashlib.sha256(source.encode()).hexdigest(), "source": source[:4500]}


async def review(output):
    params = StdioServerParameters(command=sys.executable, args=[__file__, "--serve"])
    async with stdio_client(params) as (r,w), ClientSession(r,w) as session:
        await session.initialize()
        ctx = json.loads((await session.read_resource("atlas://github/nightwatch/persistence")).contents[0].text)
    criteria = "A player should be able to quit mid-chart, reopen it at the same lights and move count, and undo the last move."
    prompt = "Review this Godot persistence implementation against the acceptance criterion. Identify one missing saved value and one concrete regression test.\n" + criteria + "\n" + ctx["source"]
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(os.environ["HUD_QWEN_URL"]+"/v1/chat/completions", json={
            "model":"qwen","messages":[{"role":"user","content":prompt}],"temperature":0,"seed":42,"max_tokens":160})
        response.raise_for_status()
        body = response.json()
    with output.open("x") as f:
        json.dump({"context":ctx,"acceptance":criteria,"model":"qwen","raw_review":body["choices"][0]["message"]["content"],
                   "finish_reason":body["choices"][0]["finish_reason"],"tokens":body["usage"]["total_tokens"]},f,indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--serve",action="store_true")
    modes.add_argument("--output",type=Path)
    args=parser.parse_args()
    if args.serve:
        server.run(transport="stdio")
    else:
        asyncio.run(review(args.output))
