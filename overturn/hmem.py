"""H-MEM: persistent memory across runs.

Local file store is the SAMPLE_MODE implementation and the offline mirror.
The Meterless adapter posts to HMEM_URL and falls back to the local mirror so
a network failure never loses the run's memories.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Settings
from .trace import Tracer


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class LocalHMem:
    engine = "local-hmem"

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._items: list[dict[str, Any]] = []
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self._items = data.get("memories", [])
            except (json.JSONDecodeError, OSError):
                self._items = []

    def _save(self) -> None:
        payload = {"version": 1, "memories": self._items}
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def remember(
        self,
        case_id: str,
        kind: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        item = {
            "memory_id": f"MEM-{len(self._items) + 1:04d}",
            "case_id": case_id,
            "kind": kind,
            "text": text,
            "metadata": metadata or {},
            "created_at": _now(),
        }
        self._items.append(item)
        self._save()
        return item

    def recall(self, case_id: str, topics: list[str] | None = None) -> list[dict[str, Any]]:
        matches = [item for item in self._items if item.get("case_id") == case_id]
        if topics:
            lowered = [t.lower() for t in topics]
            matches = [
                item
                for item in matches
                if any(
                    topic in json.dumps(item, ensure_ascii=False).lower() for topic in lowered
                )
            ]
        return sorted(matches, key=lambda item: item.get("created_at", ""), reverse=True)


class MeterlessHMem(LocalHMem):
    engine = "meterless-hmem"

    def __init__(self, settings: Settings, path: Path | str) -> None:
        super().__init__(path)
        self.settings = settings

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not self.settings.hmem_url:
            return None
        try:
            import httpx

            headers = {"Content-Type": "application/json"}
            if self.settings.hmem_api_key:
                headers["Authorization"] = f"Bearer {self.settings.hmem_api_key}"
            with httpx.Client(timeout=15.0) as client:
                response = client.post(self.settings.hmem_url + path, json=payload, headers=headers)
                if response.status_code >= 400:
                    return None
                return response.json()
        except Exception:
            return None

    def remember(
        self,
        case_id: str,
        kind: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        item = super().remember(case_id, kind, text, metadata)
        self._post("/v1/memories", item)
        return item

    def recall(self, case_id: str, topics: list[str] | None = None) -> list[dict[str, Any]]:
        # The local mirror is authoritative for the run; the engine is queried
        # for cross-session memories when reachable.
        result = self._post("/v1/memories/recall", {"case_id": case_id, "topics": topics or []})
        remote: list[dict[str, Any]] = []
        if isinstance(result, dict):
            remote = result.get("memories", []) or []
        elif isinstance(result, list):
            remote = result
        merged = {item.get("memory_id"): item for item in super().recall(case_id, topics)}
        for item in remote:
            merged.setdefault(item.get("memory_id"), item)
        return sorted(merged.values(), key=lambda item: item.get("created_at", ""), reverse=True)


def make_hmem(settings: Settings, tracer: Tracer | None = None) -> LocalHMem:
    if not settings.offline and settings.hmem_url:
        hmem: LocalHMem = MeterlessHMem(settings, settings.hmem_path)
    else:
        hmem = LocalHMem(settings.hmem_path)
    if tracer:
        tracer.event("engine", agent="system", engine=hmem.engine, decision="H-MEM ready")
    return hmem
