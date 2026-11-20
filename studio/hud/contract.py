"""A read-only MCP workspace for one team's design handoff."""
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

SLOTS = ("headline", "stage", "action")
server = FastMCP("Responsive HUD workbench")


def local_file(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Invalid design dependency")
    return path


def load(root):
    data = json.loads(local_file(root, "studio/hud-brief.json").read_text())
    components = data["components"]
    ids = {item["id"] for item in components}
    if (len(components) != 3 or len(ids) != 3 or set(data["design"]) != set(SLOTS)
            or set(data["acceptance"]) != set(SLOTS) or set(data["acceptance"].values()) != ids):
        raise ValueError("Supply one independent component and acceptance binding per region")
    if len(data["colors"]) != 2 or not all(re.fullmatch(r"[0-9a-fA-F]{6}", c) for c in data["colors"]):
        raise ValueError("Invalid screen palette")
    local_file(root, data["art"])
    for item in components:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", item["id"]):
            raise ValueError("Invalid component ID")
        if not item["symbol"] or item["symbol"] not in local_file(root, item["source"]).read_text():
            raise ValueError(f"Stale component binding: {item['id']}")
    return data


def workspace():
    return load(Path(os.environ["HUD_WORKSPACE"]).resolve())


@server.resource("studio://hud/design")
def design() -> dict:
    data = workspace()
    catalog = {item["id"]: item["description"] for item in data["components"]}
    brief = {"design": data["design"], "components": catalog}
    if len(json.dumps(brief).encode()) > 2048:
        raise ValueError("Design exceeds model context budget")
    return brief


@server.tool(structured_output=True)
def inspect_binding(region: str, component: str) -> dict[str, Any]:
    data = workspace()
    if region not in SLOTS:
        raise ValueError("Unknown region")
    return {"accepted": data["acceptance"][region] == component,
            "criterion": data["design"][region]}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


if __name__ == "__main__":
    server.run()
