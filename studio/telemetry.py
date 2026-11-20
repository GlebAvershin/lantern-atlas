# /// script
# requires-python = ">=3.11"
# dependencies = ["amplitude-analytics==1.3.0", "sentry-sdk==2.75.0"]
# ///
"""Replay actual development evidence through the two SDKs into loopback-only capture."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from amplitude import Amplitude, BaseEvent, Config
import sentry_sdk
from sentry_sdk.transport import Transport

EVIDENCE = Path(__file__).resolve().parents[1] / "evidence"


def capture():
    sdk_events = []
    issues = []

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            sdk_events.extend({"event": e["event_type"], "properties": e["event_properties"]} for e in body["events"])
            data = json.dumps({"code": 200, "events_ingested": len(body["events"])}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    class IssueCapture(Transport):
        def capture_envelope(self, envelope):
            event = envelope.get_event()
            if event:
                issues.append({"message": event.get("message"), "level": event["level"], "release": event["release"]})

    receiver = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    Thread(target=receiver.serve_forever, daemon=True).start()
    config = Config(server_url=f"http://127.0.0.1:{receiver.server_port}/2/httpapi", flush_max_retries=2)
    analytics = Amplitude("offline-authoring", configuration=config)
    recorded = json.loads((EVIDENCE/"nightwatch-authoring.json").read_text())
    try:
        for row in recorded["candidates"]:
            analytics.track(BaseEvent("nightwatch.chart_reviewed", device_id="authoring-ci",
                event_properties={"model":row["model"], "par":row["review"]["par"],
                                  "accepted":row["review"]["accepted"], "tokens":row["tokens"]}))
        analytics.flush()
        analytics.shutdown()
    finally:
        receiver.shutdown()
        receiver.server_close()
    failure = next(line for line in (EVIDENCE/"checkpoint-before.txt").read_text().splitlines() if line.startswith("FAILED:"))
    sentry_sdk.init(dsn="http://local@127.0.0.1/1", transport=IssueCapture,
                         default_integrations=False, release="nightwatch-review-10ae2f2")
    sentry_sdk.capture_message(failure, level="error")
    sentry_sdk.flush()
    sentry_sdk.get_client().close()
    passed = "Passed: true" in (EVIDENCE/"checkpoint-after.txt").read_text()
    assert len(sdk_events) == len(recorded["candidates"]) and len(issues) == 1 and passed, (len(sdk_events), len(issues), passed)
    return {"source":"release QA and authoring evidence replay", "destination":"local SDK receiver",
            "sentry_envelopes":issues, "amplitude_events":sdk_events, "checkpoint_retest_passed":passed}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = capture()
    args.output.write_text(json.dumps(result,indent=2)+"\n")
