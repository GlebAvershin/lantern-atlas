"""Estimate incremental runner and model API charges for the recorded public CPU handoff."""
import argparse
from datetime import datetime
import json
from pathlib import Path
from urllib.request import Request, urlopen

from contract import digest

TARIFF = "https://docs.github.com/en/actions/reference/runners/github-hosted-runners"


def metadata(path):
    req=Request("https://api.github.com/"+path,headers={"Accept":"application/vnd.github+json",
                                                       "User-Agent":"studio-hud-cost-review"})
    with urlopen(req,timeout=15) as response:
        return json.load(response)


def reconcile(directory):
    author=json.loads((directory/"authoring.json").read_text())
    source=json.loads((directory/"signals.json").read_text())["live_github_mcp"]
    repo="repos/GlebAvershin/"+source["repository"]
    info=metadata(repo)
    job_list=metadata(f"{repo}/actions/runs/{int(source['run'])}/jobs")
    jobs=job_list["jobs"]
    if not (info["visibility"]=="public" and len(jobs)==1 and jobs[0]["labels"]==["ubuntu-24.04"]
            and jobs[0]["head_sha"]==author["game_revision"] and jobs[0]["conclusion"]=="success"
            and author["route"]=="llama" and author["requested_model"]=="qwen"):
        raise ValueError("Run does not match the public standard-runner Qwen workflow")
    job=jobs[0]
    timestamp=lambda s:datetime.fromisoformat(s.replace("Z","+00:00"))
    seconds=(timestamp(job["completed_at"])-timestamp(job["started_at"])).total_seconds()
    report={"scope":"One completed responsive HUD job, including setup and QA. Model trace covers canonical handoff only.",
            "job":job["html_url"],"runner_labels":job["labels"],"runner_started":job["started_at"],
            "runner_finished":job["completed_at"],"runner_elapsed_seconds":seconds,"canonical_model_calls":author["model_calls"],
            "canonical_inference_tokens":author["inference_tokens"],"authoring_report_sha256":digest(author),
            "incremental_charges_usd":{"standard_public_runner_minutes":0,"external_model_api":0},
            "basis":"Published public standard-runner tariff and self-hosted GGUF inference. Excludes storage, subscriptions and developer time.",
            "tariff":TARIFF}
    (directory/"cost.json").write_text(json.dumps(report,indent=2)+"\n")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence",type=Path)
    reconcile(parser.parse_args().evidence)
