"""The Meterless adapters must perform real HTTP work, not be stubs."""

from __future__ import annotations

import json
import threading
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from overturn.config import load_settings
from overturn.hmem import make_hmem
from overturn.world_model import make_world_model


class EngineDouble(BaseHTTPRequestHandler):
    records: list[tuple[str, dict]] = []

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        EngineDouble.records.append((self.path, json.loads(raw or b"{}")))
        payload = json.dumps({"ok": True, "memories": []}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args) -> None:
        return None


def test_meterless_adapters_write_case_state_and_recall(tmp_path):
    EngineDouble.records = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), EngineDouble)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"
    settings = replace(
        load_settings("true"),
        offline=False,
        world_model_url=base_url,
        hmem_url=base_url,
        hmem_store=str(tmp_path / "hmem.json"),
    )
    try:
        world = make_world_model(settings, None, "ava")
        assert world.engine == "meterless-world-model"
        world.add_line({
            "source_table": "claim_documents",
            "source_row_id": "DOC-003",
            "date": "2026-08-20",
            "summary": "Specialist referral letter: missing",
            "verification_status": "missing",
            "confidence": 0.0,
        })
        hmem = make_hmem(settings, None)
        assert hmem.engine == "meterless-hmem"
        hmem.remember("ava", "appeal_pattern", "appeal strength 84")
        recalled = hmem.recall("ava", ["appeal"])
        assert recalled and recalled[0]["text"] == "appeal strength 84"
    finally:
        server.shutdown()
        server.server_close()

    paths = [path for path, _ in EngineDouble.records]
    assert "/v1/cases/ava/state" in paths
    assert "/v1/memories" in paths
    assert "/v1/memories/recall" in paths
    state = next(body for path, body in EngineDouble.records if path.endswith("/state"))
    assert state["case_id"] == "ava"
    assert state["lines"][0]["source_row_id"] == "DOC-003"
