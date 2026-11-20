"""Blind first-choice benchmark; the model never receives the answer key or previous verdicts."""
import argparse
import itertools
import json
from pathlib import Path
import re
import time

from contract import SLOTS, digest, load
from routes import complete

STOPWORDS = set("a an the to for from of and or in on my me are is at with how i where".split())


def words(text):
    return set(re.findall(r"[a-z0-9]+",text.lower())) - STOPWORDS


def baseline(lines, catalog):
    def score(seq):
        return sum(len(words(lines[slot]) & words(catalog[key])) for slot,key in zip(SLOTS,seq))
    # Lexical overlap plus one-to-one matching; ties use sorted identifiers.
    return dict(zip(SLOTS,max(itertools.permutations(sorted(catalog)),key=score)))


def main(args):
    design = load(args.game.resolve())
    cases = json.loads((args.game/"studio/hud-evaluation.json").read_text())
    catalog = {item["id"]: item["description"] for item in design["components"]}
    expected = design["acceptance"]
    rows = []
    for lines in cases:
        if set(lines) != set(SLOTS):
            raise ValueError("Incomplete evaluation brief")
        start = time.perf_counter_ns()
        reference = baseline(lines, catalog)
        baseline_us = (time.perf_counter_ns()-start)//1000
        result, tokens = {}, 0
        start = time.monotonic()
        for region in SLOTS:
            prompt = "Assign the most appropriate game component to this design instruction.\n" + json.dumps({
                "instruction":lines[region], "components":catalog})
            key,used = complete("llama",args.model,prompt,sorted(catalog))
            result[region] = key
            tokens += used
        rows.append({"instructions":lines,"baseline":reference,"model":result,
                     "baseline_correct":sum(reference[s]==expected[s] for s in SLOTS),
                     "model_correct":sum(result[s]==expected[s] for s in SLOTS),
                     "baseline_us":baseline_us,"model_ms":round((time.monotonic()-start)*1000),"tokens":tokens})
    report = {"project":design["project"],"model":args.model,"weights_sha256":args.weights_sha256,
              "expected":expected,"cases_sha256":digest(cases),"rows":rows}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n")


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--model",required=True)
    parser.add_argument("--weights-sha256",required=True)
    main(parser.parse_args())
