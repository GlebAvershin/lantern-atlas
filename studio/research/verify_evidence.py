"""Replay a project's saved provider traces and research results without cloud credentials."""
import argparse
import asyncio
import json
from pathlib import Path
import runpy
from uuid import NAMESPACE_URL, uuid5

from run import digest, run
from hosted_signals import recheck


def check(condition, context):
    if not condition:
        raise ValueError(context)


async def verify(game):
    folder = game / "docs/evidence"
    baseline_path = folder / "research.json"
    baseline = json.loads(baseline_path.read_text())
    paired = json.loads((folder / "research-paired.json").read_text())
    history = json.loads((folder / "research-sql.json").read_text())
    replay = run(argparse.Namespace(repository=game, hosted=False))
    for key in ("game", "query_sha256", "source_sha256", "input_rows"):
        check(baseline[key] == replay[key], f"Research changed: {key}")
    check(history["query_sha256"] == replay["query_sha256"] and history["status"] == "FINISHED"
          and history["rows_produced"] == len(replay["cases"]), "Databricks query receipt mismatch")
    check(paired["baseline_sha256"] == digest(baseline_path.read_bytes())
          and paired["features_sha256"] == digest((game / "studio/research/features.py").read_bytes())
          and paired["model"] == baseline["model"], "Paired evaluation inputs differ")
    study_dir = game / "studio/research"
    control = runpy.run_path(str(study_dir / "study.py"))["CONTROL"]
    facts = runpy.run_path(str(study_dir / "features.py"))["facts"]
    events = set()
    for local, saved, pair in zip(replay["cases"], baseline["cases"], paired["cases"], strict=True):
        name = local["scenario"]
        check(all(saved[k] == v for k, v in local.items()), f"{name}: SQL or decision mismatch")
        check(pair["scenario"] == name and pair["rule"] == local["rule"], f"{name}: paired case mismatch")
        check(saved["agreement"] == (saved["model_answer"] == local["rule"]) == pair["strict_before"]
              and pair["strict_after"] == (pair["model_answer"] == local["rule"]), f"{name}: score mismatch")
        check(pair["facts"] == facts(local["metrics"]), f"{name}: paired features differ")
        expected_services = ["amplitude"]
        if name == control or not saved["agreement"]:
            expected_services.append("sentry")
        check(sorted(r["service"] for r in saved["receipts"]) == expected_services, f"{name}: service mismatch")
        for receipt in saved["receipts"]:
            identity = f"{receipt['service']}/study-v1/{baseline['game']}/{baseline['revision']}/{replay['query_sha256']}/{name}"
            check(receipt["event_id"] == uuid5(NAMESPACE_URL, identity).hex, f"{name}: wrong event identity")
            check(receipt["http_status"] == 200 and receipt["phase"] == "ingestion_acknowledged"
                  and receipt["event_id"] not in events, f"{name}: invalid receipt")
            events.add(receipt["event_id"])

    routes = {}
    for filename, route in [("bedrock-live", "bedrock-mantle"), ("databricks-live", "databricks")]:
        trace_path = folder / f"hud/{filename}.json"
        trace = json.loads(trace_path.read_text())
        check(trace["route"] == route, f"{filename}: incorrect provider")
        calls = [row for row in trace["trace"] if row["origin"] == "inference"]
        check(len(calls) == trace["model_calls"] and calls
              and sum(row["tokens"] for row in calls) == trace["inference_tokens"], f"{route}: usage mismatch")
        result = await recheck(game, trace)
        routes[route] = {
            "model": trace["requested_model"], "trace_sha256": digest(trace_path.read_bytes()),
            "accepted_regions": result["accepted_regions"],
            "rejected_control_regions": result["rejected_control_regions"],
        }
    return {"game": replay["game"], "query_sha256": replay["query_sha256"],
            "research_cases": len(replay["cases"]),
            "research_receipts": len(events), "provider_bindings": routes}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    print(json.dumps(asyncio.run(verify(parser.parse_args().repository.resolve())), indent=2))
