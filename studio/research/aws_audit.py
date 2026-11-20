"""Audit routing and inference accounting during a recorded model outage."""
import json

SOURCE = "docs/evidence/failover-live.json"
PHASES = ("model-outage", "both-down", "model-recovery")


def load_input(root):
    trace = json.loads((root / SOURCE).read_text())
    return {phase + "/" + name: {k: row[k] for k in ("status", "served_model", "cache", "tokens", "retry_after") if k in row}
            for phase in PHASES for name, row in trace[phase].items() if isinstance(row, dict)}


def analyze(data):
    actions = {}
    billed = {}
    bad_hits = []
    for name, row in data.items():
        if row["status"] != 200:
            action = "pause_generation"
        elif row["cache"] == "hit":
            action = "serve_cache"
            if row["tokens"] != 0:
                bad_hits.append(name)
        else:
            model = row["served_model"]
            action = "use_primary" if model == "qwen" else "use_alternate"
            billed[model] = billed.get(model, 0) + row["tokens"]
        actions[name] = action
    return {"actions": actions, "generation_tokens": billed, "cache_hits_with_tokens": bad_hits,
            "retry_after_seconds": int(data["both-down/fresh"]["retry_after"])}


def verify(root, result):
    published = json.loads((root / "docs/evidence/research.json").read_text())
    previous = {case["scenario"]: case["rule"] for case in published["cases"]}
    cases = {"model-outage/interrupted": "inflight_fallback", "model-outage/cached_alternate": "alternate_warm_other_replica",
             "model-outage/pinned_primary": "pinned_primary_down", "both-down/fresh": "both_down_cold",
             "both-down/cached": "both_down_warm", "model-recovery/retry_same_request": "primary_restored",
             "model-recovery/repeat_other_replica": "restored_warm_other_replica"}
    expected = {key: previous[alias] for key, alias in cases.items()}
    expected["model-outage/warm_primary"] = "serve_cache"
    assert result["actions"] == expected and result["cache_hits_with_tokens"] == []
    assert result["retry_after_seconds"] == 5
    trace = json.loads((root / SOURCE).read_text())
    assert result["generation_tokens"] == {"qwen": trace["model-recovery"]["retry_same_request"]["tokens"],
                                           "smol": trace["model-outage"]["interrupted"]["tokens"]}
