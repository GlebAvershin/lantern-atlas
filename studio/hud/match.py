# /// script
# requires-python = ">=3.12"
# dependencies = ["mcp==1.26.0", "onnxruntime==1.31.1", "tokenizers==0.23.3", "numpy==2.5.4", "httpx==0.28.1", "pillow==12.1.1"]
# ///
"""Score the existing one-to-one matcher on the same blind instructions as the generative routes."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from contract import SLOTS, digest, load
from render import compile_page
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from retrieve import Matcher


async def main(args):
    matcher=Matcher(args.snapshot)
    cases=json.loads((args.game/"studio/hud-evaluation.json").read_text())
    server=Path(__file__).with_name("contract.py")
    params=StdioServerParameters(command=sys.executable,args=[str(server)],env={"HUD_WORKSPACE":str(args.game.resolve())})
    async with stdio_client(params) as (reader,writer),ClientSession(reader,writer) as session:
        await session.initialize()
        resource=await session.read_resource("studio://hud/design")
        brief=json.loads(resource.contents[0].text)
        catalog=brief["components"]
        rows=[]
        for lines in [*cases,brief["design"]]:
            started=time.perf_counter()
            draft=matcher.draft(catalog,"\n".join(lines[k] for k in SLOTS))
            elapsed=round((time.perf_counter()-started)*1000)
            binding=dict(zip(SLOTS,draft["rows"],strict=True))
            correct=0
            for region,component in binding.items():
                response=await session.call_tool("inspect_binding",{"region":region,"component":component})
                if response.isError or response.structuredContent is None:
                    raise RuntimeError("Verifier failed")
                correct+=int(response.structuredContent["accepted"])
            rows.append({"bindings":binding,"verified_regions":correct,"model_ms":elapsed,
                         "margin":draft["margin_over_second"]})
    handoff=rows.pop()
    handoff["rendered"]=False
    if args.screen and handoff["verified_regions"]==len(SLOTS):
        args.screen.write_text(compile_page(args.game,load(args.game.resolve()),handoff["bindings"]))
        handoff["rendered"]=True
    args.output.write_text(json.dumps({"model":"EmbeddingGemma-300M quantized ONNX CPU",
                                      "cases_sha256":digest(cases),"rows":rows,"canonical_handoff":handoff},indent=2)+"\n")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--screen",type=Path,help="Render the original handoff if every MCP check accepts it")
    parser.add_argument("--snapshot",required=True,type=Path)
    asyncio.run(main(parser.parse_args()))
