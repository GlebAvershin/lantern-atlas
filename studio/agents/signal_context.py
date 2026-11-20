"""Read-only MCP context for release triage. Operator selects the game at startup."""
from datetime import date, timedelta, timezone, datetime
import json
import os
import re

import httpx
from mcp.server.fastmcp import FastMCP

server = FastMCP("Game release signals")
GAMES = {"atlas":"lantern-atlas", "soccer":"Soccerpoly", "freight":"blackout-freight", "mosaic":"mosaic-pier"}


def github_run(client, game, run_id):
    if not str(run_id).isdigit():
        raise ValueError("Invalid workflow run ID")
    repo = GAMES[game]
    response = client.get(f"https://api.github.com/repos/GlebAvershin/{repo}/actions/runs/{run_id}")
    response.raise_for_status()
    run = response.json()
    return {"repository":repo,"run":run["id"],"revision":run["head_sha"],"state":run["status"],
            "result":run["conclusion"],"event":run["event"]}


def issues(client, org, project_id, token):
    if not re.fullmatch(r"[a-zA-Z0-9_-]+",org) or not re.fullmatch(r"[1-9][0-9]*",project_id):
        raise ValueError("Select one Sentry organization and numeric project ID")
    response = client.get(f"https://sentry.io/api/0/organizations/{org}/issues/",
        params={"project":project_id,"query":"is:unresolved","statsPeriod":"24h","limit":20},
        headers={"Authorization":"Bearer "+token})
    response.raise_for_status()
    rows = response.json()
    levels = {}
    for row in rows:
        if str(row["project"]["id"]) != project_id:
            raise ValueError("Unexpected Sentry project in response")
        level = row["level"] if row["level"] in {"error","fatal","warning","info","debug"} else "other"
        levels[level] = levels.get(level,0)+1
    return {"window":"24h","page_limit":20,"issues_on_page":len(rows),"levels":levels}


def totals(client, day, event, key, secret):
    period = date.fromisoformat(day)
    response = client.get("https://amplitude.com/api/2/events/segmentation",auth=(key,secret),
        params={"start":period.strftime("%Y%m%d"),"end":period.strftime("%Y%m%d"),
                "m":"totals","e":json.dumps({"event_type":event})})
    response.raise_for_status()
    data = response.json()["data"]
    series = data["series"]
    if data["xValues"] != [day] or len(series)!=1 or len(series[0])!=1:
        raise ValueError("Unexpected aggregation window or grouping")
    value = series[0][0]
    if type(value) not in (int,float) or value < 0 or not float(value).is_integer():
        raise ValueError("Invalid event count")
    return {"day":day,"event":event,"events":int(value)}


@server.resource("studio://signals/github")
def github() -> dict:
    with httpx.Client(timeout=10,follow_redirects=False) as client:
        return github_run(client,os.environ["STUDIO_PROJECT"],os.environ["HUD_RUN_ID"])


@server.resource("studio://signals/sentry")
def sentry() -> dict:
    with httpx.Client(timeout=10,follow_redirects=False) as client:
        return issues(client,os.environ["SENTRY_ORG"],os.environ["SENTRY_PROJECT_ID"],os.environ["SENTRY_READ_TOKEN"])


@server.resource("studio://signals/amplitude")
def amplitude() -> dict:
    # Only the previous complete UTC day and the approved review event are available to an agent.
    day = (datetime.now(timezone.utc).date()-timedelta(days=1)).isoformat()
    with httpx.Client(timeout=10,follow_redirects=False) as client:
        return totals(client,day,"game.review_accepted",os.environ["AMPLITUDE_API_KEY"],os.environ["AMPLITUDE_SECRET_KEY"])


if __name__ == "__main__":
    server.run()
