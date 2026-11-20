"""Exercise the hosted-service read contracts offline and read the selected public Actions run over MCP."""
import argparse
import asyncio
import json
from pathlib import Path
import sys

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from signal_context import GAMES, issues, totals


def test_aggregates():
    def upstream(req):
        if req.url.host=="sentry.io":
            assert req.url.path=="/api/0/organizations/team/issues/" and req.url.params["project"]=="12"
            assert req.headers["Authorization"]=="Bearer fixture"
            return httpx.Response(200,json=[{"level":"error","project":{"id":"12"},"title":"private fixture"}])
        assert req.url.host=="amplitude.com" and req.url.params["m"]=="totals"
        assert req.url.params["start"]==req.url.params["end"]=="20261119"
        assert json.loads(req.url.params["e"])["event_type"]=="game.review_accepted" and req.headers["Authorization"].startswith("Basic ")
        return httpx.Response(200,json={"data":{"series":[[4]],"xValues":["2026-11-19"],"seriesLabels":["private fixture"]}})
    with httpx.Client(transport=httpx.MockTransport(upstream)) as client:
        a=issues(client,"team","12","fixture")
        b=totals(client,"2026-11-19","game.review_accepted","fixture","fixture")
    assert a=={"window":"24h","page_limit":20,"issues_on_page":1,"levels":{"error":1}}
    assert b=={"day":"2026-11-19","event":"game.review_accepted","events":4}
    return {"source":"offline HTTP transport fixtures","sentry":a,"amplitude":b}


async def main(args):
    fixtures=test_aggregates()
    server=Path(__file__).with_name("signal_context.py")
    params=StdioServerParameters(command=sys.executable,args=[str(server)],env={
        "STUDIO_PROJECT":args.project,"HUD_RUN_ID":str(args.run)})
    async with stdio_client(params) as (reader,writer), ClientSession(reader,writer) as mcp:
        await mcp.initialize()
        resource = await mcp.read_resource("studio://signals/github")
        live = json.loads(resource.contents[0].text)
        assert live["result"]=="success" and live["run"]==args.run
    args.output.write_text(json.dumps({"live_github_mcp":live,"offline_telemetry_contracts":fixtures},indent=2)+"\n")


if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("project",choices=GAMES)
    cli.add_argument("run",type=int)
    cli.add_argument("output",type=Path)
    asyncio.run(main(cli.parse_args()))
