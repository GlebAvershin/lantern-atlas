#!/usr/bin/env python3
"""Lantern Atlas Gateway Benchmark & FinOps Token Accounting Suite.

Runs a multi-request workload evaluating:
- Cold inference vs Semantic Cache hits
- p50, p95, p99 Latency curves
- Circuit Breaker tolerance under simulated load
- Token expenditure vs Token savings (FinOps)
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "studio/agents"))

from live_platform_gateway import LivePlatformGateway

BRIEFS = [
    "Verify Beacon level 1: 3 lights, linear path, budget 4 moves.",
    "Verify Beacon level 2: 4 lights, cycle detection, budget 5 moves."
]


def run_benchmark(total_requests: int = 50) -> dict:
    gw = LivePlatformGateway()
    results = []

    print(f"[Gateway Benchmark] Executing {total_requests} requests across {len(BRIEFS)} design briefs...")

    for i in range(total_requests):
        brief = BRIEFS[i % len(BRIEFS)]
        resp = gw.generate(brief, model="databricks-qwen3-next-80b-a3b-instruct")
        results.append(resp)

    metrics = gw.get_metrics()
    
    cold_latencies = [r["latency_ms"] for r in results if r["source"] == "inference"]
    cache_latencies = [r["latency_ms"] for r in results if r["source"] == "cache"]

    def calc_percentile(arr: list[float], pct: float) -> float:
        if not arr:
            return 0.0
        sorted_arr = sorted(arr)
        idx = min(len(sorted_arr) - 1, int(len(sorted_arr) * pct))
        return round(sorted_arr[idx], 2)

    summary = {
        "workload": {
            "total_requests": total_requests,
            "unique_briefs": len(BRIEFS),
            "cold_inferences": len(cold_latencies),
            "cache_hits": len(cache_latencies),
            "cache_hit_rate": round(len(cache_latencies) / total_requests, 4)
        },
        "latency_ms": {
            "cold_p50": calc_percentile(cold_latencies, 0.50),
            "cold_p95": calc_percentile(cold_latencies, 0.95),
            "cold_p99": calc_percentile(cold_latencies, 0.99),
            "cache_p50": calc_percentile(cache_latencies, 0.50),
            "cache_p95": calc_percentile(cache_latencies, 0.95),
            "overall_p95": metrics["latency_p95_ms"]
        },
        "finops_tokens": {
            "total_tokens_billed": metrics["tokens_billed"],
            "total_tokens_saved": metrics["tokens_saved"],
            "savings_percentage": round(metrics["tokens_saved"] / (metrics["tokens_billed"] + metrics["tokens_saved"]) * 100.0, 2)
            if (metrics["tokens_billed"] + metrics["tokens_saved"]) > 0 else 0.0
        },
        "circuit_breaker": {
            "final_state": metrics["circuit_breaker_state"],
            "healthy": metrics["circuit_breaker_state"] == "CLOSED"
        }
    }
    return summary


def main():
    report = run_benchmark(50)
    out_path = ROOT / "docs/evidence/platform-gateway-benchmark.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\n[Benchmark Summary]:")
    print(f"Total Requests: {report['workload']['total_requests']} (Hit rate: {report['workload']['cache_hit_rate']*100:.1f}%)")
    print(f"Cold p95 Latency: {report['latency_ms']['cold_p95']} ms | Cache p95: {report['latency_ms']['cache_p95']} ms")
    print(f"FinOps Savings: {report['finops_tokens']['savings_percentage']}% tokens saved via semantic deduplication")
    print(f"[Evidence Saved]: {out_path}")


if __name__ == "__main__":
    main()
