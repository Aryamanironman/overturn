"""The live Zetaris REST contract, tested against a local HTTP double.

This is the exact path the Reconciler uses in live mode:
  POST {base}/api/proxy/sql-editor/sqls/run-query
  Authorization: Bearer <key>, X-Org-ID, fresh X-Request-ID
  {"sql": ..., "limit": ...}
"""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from overturn.config import load_settings
from overturn.trace import Tracer
from overturn.zetaris import SqlClient, extract_rows


class ZetarisDouble(BaseHTTPRequestHandler):
    records: list[dict] = []

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        ZetarisDouble.records.append({
            "path": self.path,
            "headers": dict(self.headers),
            "body": body,
        })
        payload = json.dumps({
            "result": {
                "columns": [{"name": "one"}],
                "rows": [[1]],
            }
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args) -> None:
        return None


def test_live_sql_contract(tmp_path):
    ZetarisDouble.records = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), ZetarisDouble)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    settings = replace(
        load_settings("true"),
        offline=False,
        zetaris_rest_url=f"http://127.0.0.1:{port}",
        zetaris_org_id="1",
        zetaris_api_key="test-key",
        zetaris_sql_path="/api/proxy/sql-editor/sqls/run-query",
        zetaris_limit=1000,
    )
    tracer = Tracer(tmp_path / "trace.jsonl")
    try:
        rows = SqlClient(settings, tracer).run_sql("SELECT 1 AS one")
    finally:
        server.shutdown()
        server.server_close()

    assert rows == [{"one": 1}]
    record = ZetarisDouble.records[0]
    assert record["path"] == "/api/proxy/sql-editor/sqls/run-query"
    assert record["headers"]["Authorization"] == "Bearer test-key"
    assert record["headers"]["X-Org-ID"] == "1"
    uuid.UUID(record["headers"]["X-Request-ID"])
    assert record["body"] == {"sql": "SELECT 1 AS one", "limit": 1000}


def test_extract_rows_shapes():
    assert extract_rows({"data": {"rows": [{"x": 2}]}}) == [{"x": 2}]
    assert extract_rows({"rows": [[3]], "columns": ["x"]}) == [{"x": 3}]
    assert extract_rows({"results": [{"y": 4}]}) == [{"y": 4}]
    assert extract_rows([{"z": 5}]) == [{"z": 5}]
