"""The single data tool: run_sql.

Zetaris is the only data path. In SAMPLE_MODE the same read-only SQL runs
against the SQLite mirror.

Live contract (from the Zetaris getting-started repo):
  POST {ZETARIS_REST_URL}{ZETARIS_SQL_PATH}
  Authorization: Bearer <API key>
  X-Org-ID: <numeric org id>
  X-Request-ID: <fresh UUID>
  body: {"sql": "...", "limit": 1000}

  Default path on a local UI-proxy install:
    /api/proxy/sql-editor/sqls/run-query
  Legacy REST install:
    ZETARIS_REST_URL=http://localhost:8888/api/v1.0
    ZETARIS_SQL_PATH=/sql-editor/sqls/run
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from .config import Settings
from .trace import Tracer, digest

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|create|alter|attach|detach|pragma|vacuum|replace|truncate|grant|revoke)\b",
    re.IGNORECASE,
)
COMMENT_LEAD = re.compile(r"^\s*(?:--[^\n]*\n\s*|/\*.*?\*/\s*)*", re.DOTALL)


class SqlError(RuntimeError):
    pass


def _strip_comments(sql: str) -> str:
    return COMMENT_LEAD.sub("", sql, count=1)


def validate_read_only(sql: str) -> str:
    cleaned = _strip_comments(sql).strip()
    if not cleaned:
        raise SqlError("empty SQL")
    body = cleaned.rstrip(";").strip()
    if ";" in body:
        raise SqlError("only one statement per run_sql call")
    first = body.split(None, 1)[0].lower()
    if first not in {"select", "with", "explain"}:
        raise SqlError(f"run_sql only accepts read-only queries, got {first.upper()}")
    match = FORBIDDEN.search(body)
    if match:
        raise SqlError(f"run_sql rejected forbidden keyword: {match.group(0)}")
    return body


def _rows_from_columns(columns: Any, rows: Any) -> list[dict[str, Any]] | None:
    if not isinstance(rows, list):
        return None
    if not rows:
        return []
    if isinstance(rows[0], dict):
        return [dict(row) for row in rows]
    if not isinstance(rows[0], (list, tuple)):
        return None
    names: list[str] = []
    if isinstance(columns, list):
        for column in columns:
            if isinstance(column, dict):
                names.append(str(column.get("name") or column.get("label") or column.get("field") or ""))
            else:
                names.append(str(column))
    if not names:
        names = [f"col_{index}" for index in range(len(rows[0]))]
    return [dict(zip(names, row)) for row in rows]


def extract_rows(data: Any, depth: int = 0) -> list[dict[str, Any]] | None:
    """Find the row set in the various Zetaris response envelopes."""
    if depth > 4:
        return None
    if isinstance(data, list):
        converted = _rows_from_columns(None, data)
        if converted is not None:
            return converted
    if isinstance(data, dict):
        columns = data.get("columns") or data.get("schema") or data.get("fields")
        for key in ("rows", "data", "results", "result", "records", "items"):
            if key not in data:
                continue
            value = data[key]
            converted = _rows_from_columns(columns, value)
            if converted is not None:
                return converted
            nested = extract_rows(value, depth + 1)
            if nested is not None:
                return nested
    return None


class SqlClient:
    def __init__(self, settings: Settings, tracer: Tracer, sample_db: Path | None = None) -> None:
        self.settings = settings
        self.tracer = tracer
        self.sample_db = Path(sample_db or settings.sample_db)
        self._token: str | None = None

    def run_sql(self, sql: str, agent: str = "reconciler") -> list[dict[str, Any]]:
        validated = validate_read_only(sql)
        engine = "sqlite-mirror" if self.settings.offline else "zetaris"
        if self.settings.offline:
            rows = self._run_sqlite(validated)
        else:
            rows = self._run_zetaris(validated)

        preview = [{k: row[k] for k in list(row)[:8]} for row in rows[:3]]
        self.tracer.event(
            "sql",
            agent=agent,
            engine=engine,
            sql=validated,
            rows=len(rows),
            rows_preview=preview,
            input_digest=digest({"sql": validated, "agent": agent, "engine": engine}),
            decision="rows_returned",
        )
        return rows

    def _run_sqlite(self, sql: str) -> list[dict[str, Any]]:
        if not self.sample_db.exists():
            raise SqlError(
                f"offline database missing at {self.sample_db}. "
                "Run: python scripts/build_sample_db.py"
            )
        conn = sqlite3.connect(f"file:{self.sample_db}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            return [dict(row) for row in conn.execute(sql).fetchall()]
        except sqlite3.Error as exc:
            raise SqlError(f"SQLite error: {exc} | SQL: {sql}") from exc
        finally:
            conn.close()

    def _token_value(self) -> str:
        if self._token:
            return self._token
        if self.settings.zetaris_api_key:
            self._token = self.settings.zetaris_api_key
            return self._token
        if not (self.settings.zetaris_username and self.settings.zetaris_password):
            raise SqlError("Zetaris credentials are missing: set ZETARIS_API_KEY or username/password")
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover
            raise SqlError("httpx is required for live Zetaris access") from exc
        try:
            with httpx.Client(timeout=self.settings.zetaris_timeout) as client:
                response = client.post(
                    self.settings.zetaris_rest_url + "/api/auth/login",
                    json={
                        "username": self.settings.zetaris_username,
                        "password": self.settings.zetaris_password,
                    },
                    headers={"X-Request-ID": str(uuid.uuid4())},
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:  # pragma: no cover
            raise SqlError(f"Zetaris login failed: {exc}") from exc
        token = None
        if isinstance(payload, dict):
            token = payload.get("idToken") or payload.get("token") or payload.get("accessToken")
        if not token:
            match = re.search(r"[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}", json.dumps(payload))
            token = match.group(0) if match else None
        if not token:
            raise SqlError("Zetaris login did not return an access token")
        self._token = str(token)
        return self._token

    def _run_zetaris(self, sql: str) -> list[dict[str, Any]]:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover
            raise SqlError("httpx is required for live Zetaris access") from exc

        url = self.settings.zetaris_rest_url.rstrip("/") + self.settings.zetaris_sql_path
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._token_value()}",
            "X-Org-ID": str(self.settings.zetaris_org_id),
            "X-Request-ID": str(uuid.uuid4()),
        }
        payload = {"sql": sql, "limit": int(self.settings.zetaris_limit)}
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                with httpx.Client(timeout=self.settings.zetaris_timeout) as client:
                    response = client.post(url, json=payload, headers=headers)
                    if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                        last_error = SqlError(f"HTTP {response.status_code}")
                        continue
                    response.raise_for_status()
                    data = response.json()
                rows = extract_rows(data)
                if rows is None:
                    raise SqlError(
                        "unrecognised Zetaris response shape: "
                        + json.dumps(data)[:500]
                    )
                return rows
            except Exception as exc:  # pragma: no cover
                last_error = exc
        raise SqlError(f"Zetaris request failed: {last_error}") from last_error
