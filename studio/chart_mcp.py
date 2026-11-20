"""Read-only game design catalogue and C++ acceptance tool for the Nightwatch event."""
import json
import os
from pathlib import Path
import subprocess
from mcp.server.fastmcp import FastMCP

server = FastMCP("Lantern Atlas chart review")
BRIEF = json.loads((Path(__file__).parent / "briefs/nightwatch.json").read_text())


@server.resource("atlas://design/nightwatch")
def design_brief() -> dict:
    return BRIEF


def oracle(width, shutters, relay, lights, taps):
    def mask(indices):
        return sum(1 << i for i in set(indices))
    args = [width, mask(shutters), *relay, lights, mask(taps)]
    run = subprocess.run([os.environ["ATLAS_ORACLE"], *map(str, args)], capture_output=True,
                         check=True, text=True, timeout=3)
    return json.loads(run.stdout)


@server.tool(structured_output=True)
def review_chart(pair: str, route: str) -> dict[str, int | bool]:
    """Check the proposed board against minimum difficulty and relay dependency."""
    relay = BRIEF["relay_pairs"][pair]
    shutters = BRIEF["shutters"]
    taps = BRIEF["routes"][route]
    initial = oracle(4, shutters, relay, 65535, taps)["scrambled"]
    audit = oracle(4, shutters, relay, initial, [])
    alternative = audit["par_without_relay"]
    return {"accepted": audit["par"] >= BRIEF["min_par"] and (alternative < 0 or alternative > audit["par"]),
            "lights": initial, "par": audit["par"], "par_without_relay": alternative}


if __name__ == "__main__":
    server.run(transport="stdio")
