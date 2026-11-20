"""Exercise both replicas, model routes and team scopes. Keep client timings with raw responses."""
import argparse
import asyncio
from collections import Counter
import json
import math
import os
from pathlib import Path
import statistics
import time
import httpx


async def probe(urls, restored):
    credentials = json.loads(os.environ["STUDIO_TOKENS"])
    by_team = {team: key for key, team in credentials.items()}
    models = ("qwen", "smol")
    async with httpx.AsyncClient(timeout=110) as client:
        async def call(index, team, model):
            start = time.perf_counter()
            response = await client.post(urls[index % 2] + "/review", json={"model": model},
                headers={"Authorization": "Bearer " + by_team[team]})
            response.raise_for_status()
            row = response.json()
            assert row["result"]["history"][-1]["verdict"]["accepted"]
            return {**row, "client_ms": round(1000 * (time.perf_counter() - start), 2)}

        denied = await client.post(urls[0] + "/review", json={"model": "qwen"},
                                   headers={"Authorization": "Bearer invalid"})
        assert denied.status_code == 401
        report = {"project": os.environ["STUDIO_PROJECT"], "unauthorized_status": denied.status_code}
        for phase in (["restored"] if restored else ["fresh", "repeat"]):
            rows = await asyncio.gather(*(call(i, "design", models[(i // 2) % 2]) for i in range(8)))
            counts = dict(Counter(row["cache"] for row in rows))
            assert len({row["worker"] for row in rows}) == 2
            for model in models:
                selected = [row for row in rows if row["model"] == model]
                assert sum(row["cache"] == "miss" for row in selected) == int(phase == "fresh")
                assert all(r["result"] == selected[0]["result"] for r in selected)
            durations = sorted(row["client_ms"] for row in rows)
            report[phase] = {"cache": counts, "tokens": sum(row["inference_tokens"] for row in rows),
                             "model_calls": sum(len(r["result"]["history"]) for r in rows if r["cache"] == "miss"),
                             "p50_ms": statistics.median(durations),
                             "p95_ms": durations[math.ceil(.95 * len(rows)) - 1], "responses": rows}
        other = await call(1, "qa", "qwen")
        assert other["cache"] == ("hit" if restored else "miss")
        report["other_team"] = other
    return report


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("output", type=Path)
    cli.add_argument("--restored", action="store_true")
    cli.add_argument("--urls", nargs=2, default=["http://127.0.0.1:18283", "http://127.0.0.1:18284"])
    args = cli.parse_args()
    data = asyncio.run(probe(args.urls, args.restored))
    args.output.write_text(json.dumps(data, indent=2) + "\n")
    for part in ("fresh","repeat","restored"):
        if part in data:
            print(part, {k:v for k,v in data[part].items() if k != "responses"})
