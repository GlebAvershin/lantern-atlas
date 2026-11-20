"""Run a game QA calculation in the AWS MCP sandbox via the installed Codex Toolkit."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import runpy
import subprocess
import time
from queue import Empty, Queue
from threading import Thread


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(data):
    return hashlib.sha256(data).hexdigest()


class CodexRPC:
    def __init__(self, process):
        self.process = process
        self.sequence = 0
        self.messages = Queue()
        Thread(target=self.read_messages, daemon=True).start()

    def read_messages(self):
        try:
            for line in self.process.stdout:
                self.messages.put(line)
        finally:
            self.messages.put(None)

    def send(self, value):
        self.process.stdin.write(json.dumps(value) + "\n")
        self.process.stdin.flush()

    def request(self, method, params):
        self.sequence += 1
        self.send({"id": self.sequence, "method": method, "params": params})
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                line = self.messages.get(timeout=max(0, deadline - time.monotonic()))
            except Empty:
                break
            if not line:
                raise RuntimeError("Codex app-server closed")
            message = json.loads(line)
            if "method" in message and "id" in message:
                raise RuntimeError(f"Unexpected interactive request: {message['method']}")
            if message.get("id") == self.sequence:
                if "error" in message:
                    raise RuntimeError(message["error"].get("message", "Codex RPC error"))
                return message["result"]
        raise TimeoutError(method)


@contextmanager
def toolkit(profile):
    plan = json.loads(subprocess.check_output(["aws", "freetier", "get-account-plan-state",
                      "--region", "us-east-1", "--profile", profile, "--output", "json"]))
    if (plan["accountPlanType"], plan["accountPlanStatus"]) != ("FREE", "ACTIVE"):
        raise ValueError("This replay expects an active AWS Free account plan")
    connection = json.loads(subprocess.check_output(["codex", "mcp", "get", "aws-mcp", "--json"]))
    transport = connection["transport"]
    if not connection["enabled"] or "--skip-auth" not in transport["args"]:
        raise ValueError("Expected the public aws-core plugin connection")
    # Use the official proxy installed by the plugin. Only this short-lived session enables computation.
    args = list(transport["args"])
    args.remove("--skip-auth")
    endpoint = "https://aws-mcp.eu-central-1.api.aws/mcp"
    args[args.index("https://aws-mcp.us-east-1.api.aws/mcp")] = endpoint
    args.extend(["--profile", profile])
    settings = ('mcp_servers.aws-game-compute={command=' + json.dumps(transport["command"]) +
                ',args=' + json.dumps(args) + ',enabled_tools=["aws___run_script"],startup_timeout_sec=120,tool_timeout_sec=120}')
    with subprocess.Popen(["codex", "app-server", "-c", settings], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE, text=True, bufsize=1) as process:
        try:
            client = CodexRPC(process)
            client.request("initialize", {"clientInfo": {"name": "game-evidence", "version": "1.0"},
                                         "capabilities": {"experimentalApi": True}})
            client.send({"method": "initialized"})
            thread = client.request("thread/start", {"ephemeral": True})["thread"]["id"]
            manifest = Path(transport["env"]["PLUGIN_ROOT"]) / ".codex-plugin/plugin.json"
            plugin = json.loads(manifest.read_text())
            yield client, thread, endpoint, {"name": plugin["name"], "version": plugin["version"], "proxy": args[0]}
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


def replay(root, client, thread, endpoint, plugin):
    spec = runpy.run_path(str(root / "studio/research/aws_audit.py"))
    data = spec["load_input"](root)
    source = inspect.getsource(spec["analyze"])
    code = source + "\nresult = analyze(json.loads(" + repr(encoded(data)) + "))\nresult"
    reply = client.request("mcpServer/tool/call", {"threadId": thread, "server": "aws-game-compute",
                           "tool": "aws___run_script", "arguments": {"code": code}})
    if reply.get("isError"):
        raise RuntimeError(f"{root.name}: AWS MCP returned an error")
    response = json.loads(reply["content"][0]["text"])
    if response["status"] != "success" or response.get("api_calls"):
        raise RuntimeError(f"{root.name}: expected successful computation with zero resource API calls")
    measured = response["return_value"]
    if measured != spec["analyze"](data):
        raise ValueError(f"{root.name}: server and local results differ")
    spec["verify"](root, measured)
    return {"tool": "aws___run_script", "plugin": plugin, "client": "Codex app-server", "endpoint": endpoint, "account_plan": "FREE / ACTIVE",
            "checked_utc": datetime.now(timezone.utc).isoformat(), "source": spec["SOURCE"],
            "source_sha256": digest((root / spec["SOURCE"]).read_bytes()), "payload_sha256": digest(encoded(data).encode()),
            "script_sha256": digest(code.encode()), "status": response["status"], "resource_api_calls": len(response.get("api_calls") or []),
            "result": measured, "local_cross_check": "passed"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("games", nargs="+", type=Path)
    options = parser.parse_args()
    if not __debug__:
        parser.error("Run with Python assertions enabled for the game checks")
    with toolkit(options.profile) as connection:
        for game in options.games:
            root = game.resolve()
            evidence = replay(root, *connection)
            path = root / "docs/evidence/aws-toolkit.json"
            path.write_text(json.dumps(evidence, indent=2) + "\n")
            print(f"{root.name}: verified {path.name}", flush=True)
