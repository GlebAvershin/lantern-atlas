"""Compare a second prompt against the same saved inputs and model, without repeating SQL or telemetry."""
import argparse
import hashlib
import json
import runpy
import subprocess
from pathlib import Path

from run import MODEL
from routes import mantle_completion


def summarize(text, options):
    first = text.strip().splitlines()[0] if text.strip() else ""
    return first if first in options else None


def evaluate(root):
    source = root / "docs/evidence/research.json"
    baseline = json.loads(source.read_text())
    plan = json.loads(subprocess.check_output(["aws","freetier","get-account-plan-state","--region","us-east-1"]))
    if (plan["accountPlanType"],plan["accountPlanStatus"]) != ("FREE","ACTIVE") or baseline["model"] != MODEL:
        raise ValueError("Expected the free account and the model used in the baseline")
    folder = root / "studio/research"
    study = runpy.run_path(str(folder/"study.py"))
    features = folder/"features.py"
    facts_for = runpy.run_path(str(features))["facts"]
    options = study["OPTIONS"]
    rows = []
    for case in baseline["cases"]:
        facts = facts_for(case["metrics"])
        prompt = (study["QUESTION"] + "\nFacts in normalized units: " + json.dumps(facts)
                  + "\nValid actions: " + ", ".join(options)
                  + "\nOutput exactly one action identifier on one line. Omit explanation.")
        result = mantle_completion(MODEL,prompt)
        answer = result["choices"][0]["message"]["content"].strip()
        expected = case["rule"]
        rows.append(dict(scenario=case["scenario"], facts=facts, rule=expected, model_answer=answer,
                         strict_before=case["agreement"], strict_after=answer==expected,
                         first_line_before=summarize(case["model_answer"],options)==expected,
                         first_line_after=summarize(answer,options)==expected, tokens=result["usage"]["total_tokens"]))
    return dict(model=MODEL, baseline_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                features_sha256=hashlib.sha256(features.read_bytes()).hexdigest(), cases=rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository",type=Path)
    print(json.dumps(evaluate(parser.parse_args().repository.resolve()), indent=2))
