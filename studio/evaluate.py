"""Measure two model routes against fixed, human-readable ordering requirements."""
import argparse
import asyncio
from collections import Counter
import json
import math
import os
from pathlib import Path
import time

import httpx

# Expected labels and the simple baseline stay on the client.
CASES = [
    ("atlas", "Chart title (logbook)\nInteractive star map (sky)\nUndo and advance (controls)", ["logbook", "sky", "controls"]),
    ("atlas", "Star map first\nUnder it, show the chart name\nPut undo at the bottom", ["sky", "logbook", "controls"]),
    ("freight", "Shift name at top\nDirection to the airlock in the middle\nBattery progress at the bottom", ["shift", "bearing", "cargo"]),
    ("freight", "Battery count first\nNext show the shift name\nLast show which way to walk", ["cargo", "shift", "bearing"]),
    ("soccer", "Club illustration\nClub name and price\nBuy or pass", ["crest", "terms", "transfer"]),
    ("soccer", "Price and terms across the top\nBuy and pass below that\nClub artwork at the bottom", ["terms", "transfer", "crest"]),
]
BASELINE = {"atlas": ["logbook", "sky", "controls"], "freight": ["shift", "bearing", "cargo"],
            "soccer": ["crest", "terms", "transfer"]}


TRANSFER = [
    ("atlas", "Undo button and next chapter action\nTap stars on a celestial grid\nTitle of the current chart", ["controls", "sky", "logbook"]),
    ("freight", "Which direction is my destination?\nBattery delivery count\nName of the active shift", ["bearing", "cargo", "shift"]),
    ("soccer", "Accept or decline the purchase\nPicture of the club emblem\nTransfer price and club name", ["transfer", "crest", "terms"]),
]


def p95(rows):
    values = sorted(row["client_ms"] for row in rows)
    return values[math.ceil(len(values) * .95) - 1] if values else None


async def main(args):
    credentials = {project: token for token, project in json.loads(os.environ["HUD_TOKENS"]).items()}
    async with httpx.AsyncClient(base_url=args.url, timeout=120) as client:
        async def request(project, wireframe, model):
            start = time.perf_counter()
            response = await client.post("/draft", json={"wireframe": wireframe, "model": model},
                                         headers={"Authorization": "Bearer " + credentials[project]})
            return {"project": project, "status": response.status_code, **response.json(),
                    "client_ms": round(1000 * (time.perf_counter() - start), 2)}

        evaluations = []
        by_model = {}
        cases = CASES + (TRANSFER if args.transfer else [])
        for model in ["qwen", "smol"]:
            trials = []
            for project, wireframe, expected in cases:
                result = await request(project, wireframe, model)
                if result.get("cache") not in (None, "miss"):
                    raise RuntimeError("Restart the gateway before capturing a new benchmark")
                trials.append({**result, "wireframe": wireframe, "expected": expected,
                               "exact": result.get("rows") == expected})
            evaluations.extend({"route": model, **trial} for trial in trials)
            by_model[model] = {"exact": sum(t["exact"] for t in trials), "n": len(trials),
                               "accepted": sum(t["status"] == 200 for t in trials), "p95_ms": p95(trials)}

        # All three projects issue simultaneous requests for their own labelled layout.
        # Specific IDs ensure the cold burst measures coalescing independent of paraphrase difficulty.
        async def burst():
            jobs = []
            for project, words in BASELINE.items():
                jobs.extend(request(project, "\n".join(words), "qwen") for _ in range(8))
            return await asyncio.gather(*jobs)

        cold, warm = await burst(), await burst()
        unauth = await client.post("/draft", json={"wireframe": "test"})
        report = {"environment": "local loopback, single gateway worker, llama.cpp, 2 slots per model",
                  "fixed_order_baseline_exact": sum(BASELINE[p] == e for p, _, e in cases),
                  "models": by_model, "trials": evaluations, "unauthenticated_status": unauth.status_code}
        for name, results in [("burst", cold), ("repeat", warm)]:
            report[name] = {"n": len(results), "cache": dict(Counter(r.get("cache", "error") for r in results)),
                            "http_ok": sum(r["status"] == 200 for r in results), "p95_ms": p95(results),
                            "tokens": sum(r.get("inference_tokens", 0) for r in results),
                            "responses": results}
        with args.output.open("x") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
        print(by_model, {k: report[k]["cache"] for k in ("burst", "repeat")})
        if unauth.status_code != 401:
            raise RuntimeError("Expected project credentials to be required")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transfer", action="store_true", help="Include three additional paraphrased layouts")
    parser.add_argument("--url", default="http://127.0.0.1:18083")
    parser.add_argument("--output", required=True, type=Path)
    asyncio.run(main(parser.parse_args()))
