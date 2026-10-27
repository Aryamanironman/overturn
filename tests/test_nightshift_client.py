"""Nightshift provider contract: headers, discovery, served model."""

from __future__ import annotations

import json
import threading
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from overturn.config import load_settings
from overturn.llm import LLMClient
from overturn.trace import Tracer


class NightshiftDouble(BaseHTTPRequestHandler):
    records: list[dict] = []

    def _send(self, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/v1/models":
            self._send({"data": [{"id": "other-model"}, {"id": "nvidia/nemotron-test"}]})
        else:
            self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        NightshiftDouble.records.append({"path": self.path, "headers": dict(self.headers), "body": body})
        self._send({
            "model": "nvidia/nemotron-test",
            "choices": [{"message": {"content": json.dumps({"ok": True})}}],
        })

    def log_message(self, *args) -> None:
        return None


def test_nightshift_headers_discovery_and_served_model(tmp_path):
    NightshiftDouble.records = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), NightshiftDouble)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    settings = replace(
        load_settings("true"),
        offline=False,
        nightshift_base_url=f"http://127.0.0.1:{port}/v1",
        nightshift_api_key="test-token",
        nightshift_app="overturn",
        nightshift_scope="user",
        models={"planner": "", "reconciler": "", "critic": "", "advocate": "", "reporter": "", "nemotron": ""},
    )
    tracer = Tracer(tmp_path / "trace.jsonl")
    try:
        result = LLMClient(settings, tracer).complete(
            agent="critic",
            kind="contract-test",
            messages=[{"role": "user", "content": "Return JSON."}],
            offline_fn=lambda: {"offline": True},
        )
    finally:
        server.shutdown()
        server.server_close()

    assert result == {"ok": True}
    post = next(record for record in NightshiftDouble.records if record["path"] == "/v1/chat/completions")
    assert post["headers"]["Authorization"] == "Bearer test-token"
    assert post["headers"]["meterless-app"] == "overturn"
    assert post["headers"]["meterless-scope"] == "user"
    assert post["body"]["model"] == "nvidia/nemotron-test"

    call = next(event for event in tracer.events if event["step"] == "agent_call")
    assert call["model"] == "nvidia/nemotron-test"
    assert call["mode"] == "live"
