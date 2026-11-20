"""Small component catalogues for designer-reviewed vertical HUD drafts."""
from mcp.server.fastmcp import FastMCP

server = FastMCP("HUD catalogue")
CATALOGUES = {
    "atlas": {
        "controls": "undo and advance buttons, guidance text",
        "logbook": "chart name and current chapter",
        "sky": "interactive star map",
    },
    "freight": {
        "cargo": "battery delivery progress",
        "bearing": "direction to the next pickup or airlock",
        "shift": "shift name and state",
    },
    "soccer": {
        "transfer": "buy or pass buttons",
        "crest": "club illustration",
        "terms": "club name, price and terms",
    },
}


@server.resource("hud://catalogue/{project}")
def catalogue(project: str) -> dict:
    """Components available to this game's layout tool."""
    return CATALOGUES[project]


@server.tool(structured_output=True)
def check_rows(project: str, rows: list[str]) -> dict[str, bool]:
    """Accept each known widget exactly once. The renderer owns dimensions and styles."""
    expected = CATALOGUES[project]
    return {"valid": len(rows) == len(expected) and set(rows) == set(expected)}


if __name__ == "__main__":
    server.run(transport="stdio")
