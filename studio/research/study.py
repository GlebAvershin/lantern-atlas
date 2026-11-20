"""Classify observed review responses across a real interruption, total outage and recovery."""
import json

SOURCE = ["docs/evidence/failover-live.json"]
COLUMNS = "scenario,status,cache_hit,alternate"
OPTIONS = ["serve_cache", "use_alternate", "use_primary", "pause_generation"]
QUESTION = ("Classify the observed response. Non-200 means pause_generation for that request. "
            "For 200, a cache hit means serve_cache regardless of model. On a miss, choose "
            "use_alternate if alternate=1, otherwise use_primary.")
CONTROL = "both_down_cold"


def samples(root):
    run = json.loads((root / SOURCE[0]).read_text())
    for phase, name, case in [
        ("model-outage", "interrupted", "inflight_fallback"),
        ("model-outage", "cached_alternate", "alternate_warm_other_replica"),
        ("model-outage", "pinned_primary", "pinned_primary_down"),
        ("both-down", "fresh", CONTROL),
        ("both-down", "cached", "both_down_warm"),
        ("model-recovery", "retry_same_request", "primary_restored"),
        ("model-recovery", "repeat_other_replica", "restored_warm_other_replica"),
    ]:
        response = run[phase][name]
        yield case, response["status"], int(response.get("cache") == "hit"), int(bool(response.get("fallback")))


def decision(metrics):
    if metrics["status"] != 200:
        return "pause_generation"
    if metrics["cache_hit"]:
        return "serve_cache"
    return "use_alternate" if metrics["alternate"] else "use_primary"
