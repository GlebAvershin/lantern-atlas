"""Run one design handoff through an included Antigravity CLI model and verify each binding over MCP."""
import argparse
import asyncio
from itertools import permutations
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contract import SLOTS, digest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"agents"))
from subscription_review import ask


async def run(args):
    params=StdioServerParameters(command=sys.executable,args=[str(Path(__file__).with_name("contract.py"))],
                                env={"HUD_WORKSPACE":str(args.game.resolve())})
    async with stdio_client(params) as (reader,writer), ClientSession(reader,writer) as mcp:
        await mcp.initialize()
        resource=await mcp.read_resource("studio://hud/design")
        design=json.loads(resource.contents[0].text)
        options={"-".join(order):dict(zip(SLOTS,order)) for order in permutations(sorted(design["components"]))}
        brief={**design,"instruction":"Choose the assignment satisfying all three design instructions.","options":options}
        with TemporaryDirectory(prefix="hud-account-") as folder:
            start=time.monotonic()
            decision=await asyncio.to_thread(ask,"gemini",args.model,brief,Path(folder))
            duration=round((time.monotonic()-start)*1000)
        assignment=options[decision["choice"]]
        accepted={}
        for region,component in assignment.items():
            response=await mcp.call_tool("inspect_binding",{"region":region,"component":component})
            if response.isError: raise RuntimeError("MCP verifier failed")
            accepted[region]=response.structuredContent["accepted"]
    result={"client":"Google Antigravity CLI","client_version":subprocess.check_output(["agy","--version"],text=True).strip(),
            "additional_credits_enabled":False,"requested_model":args.model,"brief_sha256":digest(brief),
            "elapsed_ms":duration,"answer":decision,"bindings":assignment,"mcp_acceptance":accepted}
    args.output.write_text(json.dumps(result,indent=2)+"\n")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--model",default="claude-sonnet-4-6")
    asyncio.run(run(parser.parse_args()))
