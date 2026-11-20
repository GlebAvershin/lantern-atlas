"""Recheck published HUD bindings over MCP, then optionally submit one developer QA event."""

import argparse
import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

import httpx
from contract import SLOTS
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def recheck(game):
    trace = json.loads((game / "docs/evidence/hud/authoring.json").read_text())
    project = json.loads((game / "studio/hud-brief.json").read_text())["project"]
    if trace["project"] != project:
        raise ValueError("Trace belongs to another game")
    server = Path(__file__).with_name("contract.py")
    params = StdioServerParameters(
        command=sys.executable, args=[str(server)], env={"HUD_WORKSPACE": str(game)}
    )
    async with (
        stdio_client(params) as (reader, writer),
        ClientSession(reader, writer) as session,
    ):
        await session.initialize()
        design = json.loads(
            (await session.read_resource("studio://hud/design")).contents[0].text
        )
        digest = hashlib.sha256(json.dumps(design, sort_keys=True).encode()).hexdigest()
        if digest != trace["brief_sha256"]:
            raise ValueError("Published trace is stale for this design")
        for key, expected in [("bindings", True), ("negative_control", False)]:
            for slot in SLOTS:
                reply = await session.call_tool(
                    "inspect_binding", {"region": slot, "component": trace[key][slot]}
                )
                if (
                    reply.isError
                    or not reply.structuredContent
                    or reply.structuredContent["accepted"] is not expected
                ):
                    raise ValueError(f"Unexpected MCP result for {key}/{slot}")
    revision = (
        await asyncio.to_thread(
            subprocess.check_output, ["git", "-C", game, "rev-parse", "HEAD"], text=True
        )
    ).strip()
    return {
        "game": project,
        "revision": revision,
        "brief_sha256": digest,
        "accepted_regions": len(SLOTS),
        "rejected_control_regions": len(SLOTS),
        "source": "developer_qa",
    }


def submit(client, service, context, event_id, timestamp, region):
    if service == "amplitude":
        host = {"us": "api2.amplitude.com", "eu": "api.eu.amplitude.com"}[region]
        event = {
            "event_type": "game.review_accepted",
            "device_id": "portfolio-hud-qa",
            "insert_id": event_id,
            "time": int(timestamp.timestamp() * 1000),
            "event_properties": context,
        }
        response = client.post(
            f"https://{host}/2/httpapi",
            json={"api_key": os.environ["AMPLITUDE_API_KEY"], "events": [event]},
        )
    else:
        dsn = os.environ["SENTRY_DSN"]
        parsed = urlsplit(dsn)
        if (
            parsed.scheme != "https"
            or not parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.port
            or not re.fullmatch(
                r"o\d+\.ingest(?:\.[a-z]+)?\.sentry\.io", parsed.hostname or ""
            )
            or not re.fullmatch(r"/\d+", parsed.path)
        ):
            raise ValueError("Expected the test project's Sentry Cloud DSN")
        item = {
            "event_id": event_id,
            "timestamp": timestamp.isoformat(),
            "platform": "python",
            "level": "warning",
            "message": "HUD verifier rejected the rotated negative control",
            "environment": "portfolio-qa",
            "release": context["revision"],
            "tags": {"game": context["game"], "source": "developer_qa"},
            "fingerprint": ["portfolio-hud-negative-control", context["game"]],
            "extra": context,
        }
        envelope = "\n".join(
            json.dumps(line)
            for line in [{"event_id": event_id, "dsn": dsn}, {"type": "event"}, item]
        )
        response = client.post(
            f"https://{parsed.hostname}/api{parsed.path}/envelope/",
            content=(envelope + "\n").encode(),
            headers={"Content-Type": "application/x-sentry-envelope"},
        )
    if response.status_code != 200:
        raise RuntimeError(f"{service} ingestion returned HTTP {response.status_code}")
    body = response.json()
    if service == "amplitude" and (
        body.get("code") != 200 or body.get("events_ingested") != 1
    ):
        raise RuntimeError("Amplitude did not acknowledge exactly one event")
    if service == "sentry" and body.get("id") != event_id:
        raise RuntimeError("Sentry did not acknowledge this event ID")
    return {
        "service": service,
        "phase": "ingestion_acknowledged",
        "http_status": response.status_code,
        "event_id": event_id,
        "timestamp_utc": timestamp.isoformat(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", type=Path)
    parser.add_argument("service", choices=("prepare", "sentry", "amplitude"))
    parser.add_argument(
        "--region",
        choices=("us", "eu"),
        default="us",
        help="Amplitude project data region",
    )
    args = parser.parse_args()
    context = asyncio.run(recheck(args.game.resolve()))
    result = {"mcp": context}
    if args.service != "prepare":
        identity = f"{args.service}/hud-control/{context['game']}/{context['revision']}/{context['brief_sha256']}"
        with httpx.Client(timeout=15, follow_redirects=False) as client:
            result["receipt"] = submit(
                client,
                args.service,
                context,
                uuid5(NAMESPACE_URL, identity).hex,
                datetime.now(UTC),
                args.region,
            )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
