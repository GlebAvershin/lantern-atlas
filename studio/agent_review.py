"""Compare finale candidates with the independent C++ solver used in release QA."""
from mcp.server.fastmcp import FastMCP
from chart_mcp import BRIEF, review_chart

server = FastMCP("Nightwatch route review")
OPTIONS = {"short_crossing": ["horizon", "shoal"], "coastal_route": ["horizon", "crossing"],
           "crescent_passage": ["channel", "crescent"]}


@server.resource("studio://review/brief")
def brief() -> dict:
    return {"instruction": "Recommend a finale requiring a distant relay and at least five moves. "
                           "The designer accepts either qualifying route.",
            "options": OPTIONS, "facts": BRIEF}


@server.tool(structured_output=True)
def verify_choice(choice: str) -> dict:
    if choice not in OPTIONS:
        return {"accepted": False, "reason": "Unknown chart"}
    return review_chart(*OPTIONS[choice])


if __name__ == "__main__":
    server.run()
