"""Run a local CLI account against a single game's public studio review contract."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ADAPTERS = {"atlas": "studio/agent_review.py", "soccer": "scripts/agent_review.py",
            "freight": "analysis/agent_review.py"}
DEFAULT_MODELS = {"codex": "gpt-6.2-sol", "gemini": "gemini-3.8-flash-low"}
PROMPT = ("Review this game design brief. Use only the supplied data, without tools. "
          "Choose exactly one listed option. Explain the decision in one short English sentence.\n")


def account_environment():
    # Each CLI owns its interactive login. Never send account tokens through the game's MCP server.
    allowed = ("HOME", "PATH", "USER", "LOGNAME", "LANG", "TMPDIR", "SYSTEMROOT", "LOCALAPPDATA", "APPDATA")
    return {key: os.environ[key] for key in allowed if key in os.environ}


def ask(provider, model, brief, work):
    schema = {"type": "object", "additionalProperties": False, "required": ["choice", "reason"],
              "properties": {"choice": {"type": "string", "enum": list(brief["options"])},
                             "reason": {"type": "string"}}}
    schema_path = work / "decision.schema.json"
    schema_path.write_text(json.dumps(schema))
    env = account_environment()
    text = PROMPT + json.dumps(brief, sort_keys=True)
    if provider == "codex":
        status = subprocess.run(["codex", "login", "status"], capture_output=True, text=True, env=env, timeout=15)
        if status.returncode or "logged in using chatgpt" not in (status.stdout + status.stderr).lower():
            raise RuntimeError("Run codex login and sign in with ChatGPT.")
        result = work / "decision.json"
        command = ["codex", "exec", "--ignore-user-config", "--ephemeral", "--skip-git-repo-check",
                   "--sandbox", "read-only", "-c", 'model_provider="openai"', "-m", model,
                   "--output-schema", str(schema_path), "-o", str(result), "-"]
    else:
        settings = {"modelProvider": "", "useG1Credits": False, "allowNonWorkspaceAccess": False,
                    "toolPermission": "strict"}
        command = ["agy", "--model", model, "--mode", "plan", "--disable-slash-commands",
                   "--settings", json.dumps(settings), "--print-timeout", "90s",
                   "--json-schema", str(schema_path), "--output-format", "json", "--print", text]
    run = subprocess.run(command, cwd=work, env=env, text=True, input=text if provider == "codex" else "",
                         capture_output=True, timeout=150)
    if run.returncode:
        # CLI diagnostics can include account details. Keep them out of portfolio files.
        raise RuntimeError(f"{provider} CLI exited with status {run.returncode}. Check its login, model and quota.")
    raw = result.read_text() if provider == "codex" else run.stdout
    payload = json.loads(raw)
    answer = payload if provider == "codex" else payload["structured_output"]
    if answer.get("choice") not in brief["options"] or not isinstance(answer.get("reason"), str) or not answer["reason"].strip():
        raise ValueError("CLI response does not match the game contract")
    return {"choice": answer["choice"], "reason": answer["reason"]}


async def review(args):
    game = args.game_root.resolve()
    adapter = ADAPTERS[args.game]
    tool_python = game / "analysis/.venv/bin/python" if args.game == "freight" else Path(sys.executable)
    model = args.model or DEFAULT_MODELS[args.provider]
    with TemporaryDirectory(prefix="studio-subscription-") as directory:
        work = Path(directory)
        tool_env = {}
        if args.game == "atlas":
            oracle = work / "oracle"
            subprocess.run(["c++", "-std=c++17", "-O2", str(game/"studio/oracle.cpp"), "-o", str(oracle)], check=True)
            # Run once outside the interactive MCP deadline (new macOS binaries may start slowly).
            subprocess.run([str(oracle), "3", "0", "-1", "-1", "511", "0"],
                           check=True, stdout=subprocess.DEVNULL, timeout=30)
            tool_env["ATLAS_ORACLE"] = str(oracle)
        params = StdioServerParameters(command=str(tool_python), args=[str(game/adapter)], env=tool_env)
        async with stdio_client(params) as (reader, writer), ClientSession(reader, writer) as mcp:
            await mcp.initialize()
            resource = await mcp.read_resource("studio://review/brief")
            brief = json.loads(resource.contents[0].text)
            started = time.monotonic()
            cli_work = work / "client"
            cli_work.mkdir()
            answer = await asyncio.to_thread(ask, args.provider, model, brief, cli_work)
            duration = round((time.monotonic() - started) * 1000)
            verdict = await mcp.call_tool("verify_choice", {"choice": answer["choice"]})
            if verdict.isError or not isinstance(verdict.structuredContent, dict):
                raise ValueError(f"MCP game verifier failed: {verdict.content}")
            decision = verdict.structuredContent
    cli = "codex" if args.provider == "codex" else "agy"
    return {"game": args.game, "provider": args.provider, "requested_model": model,
            "cli_version": subprocess.check_output([cli, "--version"], text=True).strip(),
            "game_revision": subprocess.check_output(["git", "-C", game, "rev-parse", "HEAD"], text=True).strip(),
            "brief_sha256": hashlib.sha256(json.dumps(brief, sort_keys=True).encode()).hexdigest(),
            "cli_elapsed_ms": duration, "answer": answer, "verdict": decision}


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--game", choices=ADAPTERS, required=True)
    cli.add_argument("--game-root", type=Path, required=True)
    cli.add_argument("--provider", choices=DEFAULT_MODELS, required=True)
    cli.add_argument("--model")
    args = cli.parse_args()
    report = asyncio.run(review(args))
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["verdict"].get("accepted") is True else 1)
