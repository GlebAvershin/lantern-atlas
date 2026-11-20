"""Bind real game components to a design, then use the MCP verifier before rendering."""
import argparse
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from contract import SLOTS, digest, load
from render import compile_page
from routes import complete, gateway_policy


async def author(root, out, route, model, inspect_gateway=False):
    root = root.resolve()
    design = load(root)
    params = StdioServerParameters(command=sys.executable, args=[str(Path(__file__).with_name("contract.py"))],
                                   env={"HUD_WORKSPACE": str(root)})
    policy = await asyncio.to_thread(gateway_policy, model) if inspect_gateway else None
    binding, trace = {}, []
    async with stdio_client(params) as (reader, writer), ClientSession(reader, writer) as mcp:
        await mcp.initialize()
        resource = await mcp.read_resource("studio://hud/design")
        brief = json.loads(resource.contents[0].text)

        async def inspect(region, name):
            verdict = await mcp.call_tool("inspect_binding", {"region": region, "component": name})
            if verdict.isError or not isinstance(verdict.structuredContent, dict):
                raise RuntimeError("MCP verifier failed")
            return verdict.structuredContent["accepted"]

        control = {slot: design["acceptance"][SLOTS[(idx+1) % len(SLOTS)]] for idx, slot in enumerate(SLOTS)}
        rejected = [slot for slot in SLOTS if not await inspect(slot, control[slot])]
        if len(rejected) != len(SLOTS):
            raise RuntimeError("Verifier accepted a rotated binding")
        started = time.monotonic()
        for region in SLOTS:
            remaining = set(brief["components"]) - set(binding.values())
            while remaining:
                choices = sorted(remaining)
                if len(choices) == 1:
                    selected, tokens, origin = choices[0], 0, "elimination"
                else:
                    context = {"design_instruction": brief["design"][region], "region": region,
                               "available_components": {k: brief["components"][k] for k in choices}}
                    prompt = "Select the game component that satisfies the region in this design.\n" + json.dumps(context)
                    selected, tokens = await asyncio.to_thread(complete, route, model, prompt, choices)
                    origin = "inference"
                ok = await inspect(region, selected)
                trace.append(dict(region=region, component=selected, origin=origin, tokens=tokens, accepted=ok))
                if ok:
                    binding[region] = selected
                    break
                remaining.remove(selected)
            else:
                raise ValueError(f"No accepted component for {region}")
        elapsed = round((time.monotonic() - started)*1000)
    out.mkdir(parents=True, exist_ok=True)
    (out/"screen.html").write_text(compile_page(root, design, binding))
    report = {"project": design["project"], "screen": design["screen"], "route": route, "requested_model": model,
              "game_revision": subprocess.check_output(["git", "-C", root, "rev-parse", "HEAD"], text=True).strip(),
              "brief_sha256": digest(brief), "bindings": binding, "negative_control": control,
              "rejected_control_regions": rejected, "trace": trace, "model_calls": sum(t["origin"]=="inference" for t in trace),
              "inference_tokens": sum(t["tokens"] for t in trace), "authoring_ms": elapsed}
    if inspect_gateway:
        report["databricks_ai_gateway"] = policy
    (out/"authoring.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--route", choices=("llama","bedrock","databricks"), default="llama")
    parser.add_argument("--model", required=True)
    parser.add_argument("--inspect-gateway",action="store_true",help="Read and record the Databricks AI Gateway configuration")
    args = parser.parse_args()
    if args.inspect_gateway and args.route != "databricks":
        parser.error("--inspect-gateway requires the Databricks route")
    asyncio.run(author(args.root, args.out, args.route, args.model,args.inspect_gateway))
