"""Classify partial and total model outages using targeted probes from a real CI replay."""
import json

SOURCE = ["docs/evidence/mixed-recovery.json"]
COLUMNS = "scenario,probe,status"
OPTIONS = ["use_alternate", "pause_generation", "use_primary"]
QUESTION = ("Choose use_primary if its fresh probe succeeds. Otherwise choose use_alternate if its "
            "fresh probe succeeds. If both fresh probes fail, pause generation. A cache hit "
            "only proves previously generated content can be read. Status values are HTTP codes.")
CONTROL = "both_fresh_failed"


def samples(root):
    run = json.loads((root / SOURCE[0]).read_text())
    outage = run["model-outage"]
    original = {"fresh_primary": outage["uncached_during_outage"]["status"],
                "cached_primary": outage["cached_during_outage"]["status"],
                "fresh_alternate": outage["other_model_during_outage"]["status"]}
    for scenario, probes in [("recorded_outage", original),
                             (CONTROL, {**original, "fresh_alternate": 502}),
                             ("primary_restored_replay", {**original, "fresh_primary":
                                  run["model-recovery"]["retry_same_request"]["status"]})]:
        for kind, status in probes.items():
            yield scenario, kind, status


def decision(metrics):
    if metrics["fresh_primary"] == 200:
        return OPTIONS[2]
    return OPTIONS[0] if metrics["fresh_alternate"] == 200 else OPTIONS[1]
