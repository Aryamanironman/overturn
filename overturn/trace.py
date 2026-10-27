"""First-class tracing: every hop is an event in out/trace.jsonl."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class Tracer:
    """Append-only JSONL tracer. Also keeps events in memory for the receipt."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else None
        self.events: list[dict] = []
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("", encoding="utf-8")

    def event(self, step: str, **fields: Any) -> dict:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "step": step,
        }
        for key, value in fields.items():
            if value is not None:
                record[key] = value
        self.events.append(record)
        if self.path:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(canonical_json(record) + "\n")
        return record

    def close(self) -> None:
        return None
