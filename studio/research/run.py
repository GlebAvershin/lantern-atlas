"""Run one repository's game study locally, or compare it with a free cloud workspace."""
import argparse
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import runpy
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hud"))

MODEL = "qwen.qwen3-coder-30b-a3b-instruct"


def digest(value):
    return hashlib.sha256(value).hexdigest()


def query_for(folder, columns, rows):
    # All inputs come from the checked-in game study; encode values through SQLite itself.
    with sqlite3.connect(":memory:") as db:
        literals = [[db.execute("SELECT quote(?)", (v,)).fetchone()[0] for v in row] for row in rows]
    values = ",\n".join("(" + ",".join(row) + ")" for row in literals)
    return f"WITH samples({columns}) AS (VALUES {values})\n" + (folder / "metrics.sql").read_text()


def cloud_rows(query, warehouse, profile):
    def api(method, path, body=None):
        command = ["databricks", "api", method, path, "-p", profile, "-o", "json"]
        if body is not None:
            command.extend(["--json", json.dumps(body)])
        return json.loads(subprocess.check_output(command))

    path = "/api/2.0/sql/statements"
    response = api("post", path, {"warehouse_id": warehouse, "statement": query,
                                  "wait_timeout": "10s", "on_wait_timeout": "CONTINUE"})
    deadline = time.monotonic() + 180
    while response["status"]["state"] in ("PENDING", "RUNNING") and time.monotonic() < deadline:
        time.sleep(2)
        response = api("get", f"{path}/{response['statement_id']}")
    if response["status"]["state"] != "SUCCEEDED":
        raise RuntimeError(response["status"])
    manifest = response["manifest"]
    rows = response.get("result", {}).get("data_array", [])
    if manifest.get("truncated") or len(rows) != manifest["total_row_count"]:
        raise ValueError("Expected one complete inline result")
    return [c["name"] for c in manifest["schema"]["columns"]], [[r[0], *map(int, r[1:])] for r in rows]


def run(args):
    game = args.repository.resolve()
    folder = game / "studio/research"
    study = runpy.run_path(str(folder / "study.py"))
    samples = list(study["samples"](game))
    query = query_for(folder, study["COLUMNS"], samples)
    with sqlite3.connect(":memory:") as db:
        cursor = db.execute(query)
        columns = [col[0] for col in cursor.description]
        rows = [list(row) for row in cursor]
    revision = subprocess.check_output(["git", "-C", game, "rev-parse", "HEAD"], text=True).strip()
    title = json.loads((game / "studio/hud-brief.json").read_text())["project"]
    report = dict(game=title, revision=revision, source_sha256={p: digest((game/p).read_bytes())
                  for p in [*study["SOURCE"], "studio/research/study.py", "studio/research/metrics.sql"]},
                  query_sha256=digest(query.encode()), input_rows=len(samples), cases=[])
    if "calibration_table" in study:
        report["budget_sweep"] = study["calibration_table"](samples)
    if args.hosted:
        import httpx
        from hosted_signals import submit
        from routes import mantle_completion

        plan = json.loads(subprocess.check_output(["aws", "freetier", "get-account-plan-state",
                          "--region", "us-east-1", "--output", "json"]))
        if (plan["accountPlanType"], plan["accountPlanStatus"]) != ("FREE", "ACTIVE"):
            raise ValueError("This study requires an active free AWS account")
        actual = cloud_rows(query, os.environ["DATABRICKS_WAREHOUSE_ID"], os.environ["DATABRICKS_CONFIG_PROFILE"])
        if actual != (columns, rows):
            raise ValueError("Cloud and local results differ")
        report.update(databricks="SQL Statement Execution / SQLite parity", aws_plan="FREE / ACTIVE",
                      model=MODEL, region=os.environ["AWS_DEFAULT_REGION"], utc=datetime.now(timezone.utc).isoformat())
    with (httpx.Client(timeout=20) if args.hosted else nullcontext()) as client:
        for scenario, *values in rows:
            metrics = dict(zip(columns[1:], values, strict=True))
            decision = study["decision"](metrics)
            case = dict(scenario=scenario, metrics=metrics, rule=decision)
            report["cases"].append(case)
            if not args.hosted:
                continue
            prompt = (study["QUESTION"] + "\nMeasurements: " + json.dumps(metrics) +
                      "\nChoose exactly one of " + json.dumps(study["OPTIONS"]) + ". Return only the choice.")
            result = mantle_completion(MODEL, prompt)
            answer = result["choices"][0]["message"]["content"].strip()
            case.update(model_answer=answer, agreement=answer==decision, tokens=result["usage"]["total_tokens"])
            context = dict(game=title, revision=revision, scenario=scenario, source="developer_qa",
                           rule=decision, agreement=case["agreement"], **metrics)
            case["receipts"] = []
            services = ["amplitude"]
            if scenario == study["CONTROL"] or not case["agreement"]:
                services.append("sentry")
            for service in services:
                identity = f"{service}/study-v1/{title}/{revision}/{report['query_sha256']}/{scenario}"
                receipt = submit(client, service, context, uuid5(NAMESPACE_URL,identity).hex,
                                 datetime.now(timezone.utc), args.amplitude_region, event_type="game.study_evaluated",
                                 warning=f"{title} research check: {scenario} / {decision}",
                                 group=f"game-study/{scenario}")
                case["receipts"].append(receipt)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    parser.add_argument("--hosted", action="store_true")
    parser.add_argument("--amplitude-region", choices=["eu","us"], default="us")
    args = parser.parse_args()
    print(json.dumps(run(args), indent=2, ensure_ascii=False))
