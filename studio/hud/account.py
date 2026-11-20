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
        history=[]
        if args.previous:
            prior=json.loads(args.previous.read_text())
            if prior["brief_sha256"] != digest(brief) or prior["requested_model"] != args.model:
                raise ValueError("Previous attempt belongs to a different model or brief")
        for attempt in range(2):
            origin="account_inference"
            if len(brief["options"])==1:
                origin="verifier_elimination"
                decision={"choice":next(iter(brief["options"])),"reason":"Only one assignment satisfies the previous verification."}
                duration=0
            elif attempt == 0 and args.previous:
                decision,duration=prior["answer"],prior["elapsed_ms"]
            else:
                with TemporaryDirectory(prefix="hud-account-") as folder:
                    start=time.monotonic()
                    decision=await asyncio.to_thread(ask,"gemini",args.model,brief,Path(folder))
                    duration=round((time.monotonic()-start)*1000)
            assignment=brief["options"][decision["choice"]]
            accepted={}
            for region,component in assignment.items():
                response=await mcp.call_tool("inspect_binding",{"region":region,"component":component})
                if response.isError: raise RuntimeError("MCP verifier failed")
                accepted[region]=response.structuredContent["accepted"]
            history.append({"origin":origin,"brief_sha256":digest(brief),"elapsed_ms":duration,"answer":decision,
                            "bindings":assignment,"mcp_acceptance":accepted})
            if all(accepted.values()) or attempt == 1:
                break
            survivors=[value for value in options.values() if all(
                (value[region]==assignment[region])==passed for region,passed in accepted.items())]
            # Retain the verifier feedback. Use short identifiers so a plausible explanation
            # cannot be mistaken for a valid returned permutation.
            brief={**design,"instruction":"Choose the remaining valid assignment by its listed ID.",
                   "prior_review":{"bindings":assignment,"mcp_acceptance":accepted},
                   "options":{f"layout_{n}":value for n,value in enumerate(survivors,1)}}
        result={"client":"Google Antigravity CLI","client_version":subprocess.check_output(["agy","--version"],text=True).strip(),
                "additional_credits_enabled":False,"requested_model":args.model,**history[-1],"attempts":history}
    args.output.write_text(json.dumps(result,indent=2)+"\n")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--previous",type=Path,help="Recheck and resume one saved first attempt")
    parser.add_argument("--model",default="claude-sonnet-4-6")
    asyncio.run(run(parser.parse_args()))
