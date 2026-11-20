"""Exercise the actual release wireframe across ten simultaneous designer requests."""
import argparse
import asyncio
from collections import Counter
import json
import math
import os
from pathlib import Path
import time
import httpx


async def main(url, output):
    wireframe = (Path(__file__).parent / "briefs/hud.txt").read_text().strip()
    tokens = json.loads(os.environ["HUD_TOKENS"])
    project_token = next(token for token, project in tokens.items() if project == "atlas")
    async with httpx.AsyncClient(base_url=url, timeout=120) as client:
        async def draft():
            start = time.perf_counter()
            r = await client.post("/draft", json={"wireframe": wireframe, "model": "qwen"},
                                  headers={"Authorization": "Bearer " + project_token})
            r.raise_for_status()
            return {**r.json(), "client_ms": round(1000*(time.perf_counter()-start), 2)}
        report = {"wireframe": wireframe}
        for batch in ("fresh", "warm"):
            rows = await asyncio.gather(*(draft() for _ in range(10)))
            report[batch] = {"outcomes": dict(Counter(row["cache"] for row in rows)),
                             "p95_ms": sorted(row["client_ms"] for row in rows)[math.ceil(.95*len(rows))-1],
                             "inference_tokens": sum(row["inference_tokens"] for row in rows), "requests": rows}
        assert report["fresh"]["outcomes"].get("miss") == 1
        assert report["warm"]["outcomes"] == {"hit": 10}
        assert report["warm"]["inference_tokens"] == 0
        report["matches_design"] = report["fresh"]["requests"][0]["rows"] == ["logbook", "sky", "controls"]
        output.write_text(json.dumps(report, indent=2) + "\n")
        for phase in ("fresh", "warm"):
            print(phase, {k:v for k,v in report[phase].items() if k != "requests"})
        print("Matches design:", report["matches_design"])


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--url", default="http://127.0.0.1:18083")
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    asyncio.run(main(args.url, args.output))
