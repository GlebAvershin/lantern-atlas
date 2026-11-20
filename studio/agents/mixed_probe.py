"""Exercise curated finale briefs, independent teams and a live model interruption on a disposable runner."""
import argparse
import asyncio
from collections import Counter
import itertools
import json
import math
import os
from pathlib import Path
import random
import signal
import time

import httpx

BRIEFS = [
    ["short_crossing", "coastal_route"],
    ["short_crossing", "crescent_passage"],
    ["coastal_route", "crescent_passage"],
]
INTERRUPTED = ["coastal_route"]
MODELS = ("qwen", "smol")


async def probe(args):
    tokens = {team: key for key, team in json.loads(os.environ["STUDIO_TOKENS"]).items()}
    async with httpx.AsyncClient(timeout=100) as client:
        async def call(team, model, choices, replica, allow_fallback=True):
            start = time.perf_counter()
            r = await client.post(f"http://127.0.0.1:{18283 + replica}/review",
                json={"model": model, "candidates": choices, "allow_fallback": allow_fallback}, headers={"Authorization": "Bearer " + tokens[team]})
            row = {"team": team, "model": model, "choices": choices, "replica": replica, "status": r.status_code,
                   "client_ms": round((time.perf_counter() - start) * 1000, 2)}
            if r.status_code == 503:
                row["retry_after"] = r.headers.get("Retry-After")
            if r.is_success:
                body = r.json()
                result = body["result"]
                assert result["choice"] in choices and result["history"][-1]["verdict"]["accepted"]
                row.update(served_model=body["model"], fallback=body["fallback"], cache=body["cache"], choice=result["choice"], worker=body["worker"],
                           tokens=body["inference_tokens"], attempts=len(result["history"]))
            return row

        if args.phase == "recover":
            retry = await call("design", "qwen", INTERRUPTED, 1)
            repeat = await call("design", "qwen", INTERRUPTED, 0)
            assert retry["served_model"] == "qwen" and not retry["fallback"]
            assert retry.get("cache") == "miss" and repeat.get("cache") == "hit"
            return {"retry_same_request": retry, "repeat_other_replica": repeat}

        if args.phase == "outage":
            # The caller supplies the PID of its own temporary llama-server. Wait for actual inference.
            pending = asyncio.create_task(call("design", "qwen", INTERRUPTED, 0))
            async with asyncio.timeout(20):
                while True:
                    slots = await client.get(args.qwen_url + "/slots")
                    slots.raise_for_status()
                    if any(s["is_processing"] for s in slots.json()):
                        break
                    if pending.done():
                        raise RuntimeError("Request completed before a busy inference slot was observed")
                    await asyncio.sleep(.01)
            os.kill(args.runner_model_pid, signal.SIGKILL)
            failed = await pending
            assert failed["status"] == 200 and failed["served_model"] == "smol" and failed["fallback"]
            assert failed["cache"] == "miss" and failed["tokens"] > 0
            warm, pinned, reused = await asyncio.gather(
                call("design", "qwen", BRIEFS[0], 1), call("qa", "qwen", INTERRUPTED, 1, False),
                call("design", "qwen", INTERRUPTED, 1))
            assert warm["cache"] == "hit" and not warm["fallback"] and pinned["status"] == 502
            assert reused["served_model"] == "smol" and reused["cache"] == "hit" and reused["tokens"] == 0
            return {"busy_slot_confirmed": True, "interrupted": failed, "warm_primary": warm,
                    "pinned_primary": pinned, "cached_alternate": reused}

        if args.phase == "both-down":
            cold = await call("qa", "qwen", ["crescent_passage"], 1)
            warm = await call("design", "qwen", BRIEFS[0], 0)
            assert cold["status"] == 503 and cold["retry_after"] == "5"
            assert warm["cache"] == "hit" and warm["tokens"] == 0
            return {"fresh": cold, "cached": warm}

        bad = await call("design", "qwen", ["unknown"], 0)
        duplicate = await call("qa", "smol", ["coastal_route", "coastal_route"], 1)
        assert bad["status"] == duplicate["status"] == 422
        combinations = list(itertools.product(sorted(tokens), MODELS, range(len(BRIEFS))))
        records = []
        for batch in range(10):
            jobs = combinations.copy()
            random.Random(123 + batch).shuffle(jobs)
            rows = await asyncio.gather(*(call(team, model, BRIEFS[i], (batch + combinations.index((team, model, i))) % 2)
                                          for team, model, i in jobs))
            for row in rows:
                row["batch"] = batch
            records.extend(rows)
        assert all(r["status"] == 200 for r in records)
        for team, model, i in combinations:
            subset = [r for r in records if r["team"] == team and r["model"] == model and r["choices"] == BRIEFS[i]]
            assert Counter(r["cache"] for r in subset) == {"miss": 1, "hit": 9}
            assert len({r["worker"] for r in subset}) == 2
        def summary(rows):
            latency = sorted(r["client_ms"] for r in rows)
            return {"n": len(rows), "p95_ms": latency[math.ceil(.95 * len(rows)) - 1],
                    "tokens": sum(r["tokens"] for r in rows), "cache": dict(Counter(r["cache"] for r in rows))}
        return {"invalid_requests": [bad, duplicate], "all": summary(records),
                "first_batch": summary(records[:12]), "repeated": summary(records[12:]), "requests": records}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("load", "outage", "both-down", "recover"))
    parser.add_argument("output", type=Path)
    parser.add_argument("--runner-model-pid", type=int)
    parser.add_argument("--qwen-url")
    args = parser.parse_args()
    if args.phase == "outage" and (not args.qwen_url or not args.runner_model_pid or args.runner_model_pid <= 1):
        parser.error("Outage test needs the runner-owned model PID and its private endpoint")
    result = asyncio.run(probe(args))
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print({key: value for key, value in result.items() if key != "requests"})
