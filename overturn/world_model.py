"""Shared ledger state.

The World Model is the one object the Reconciler and Critic both mutate and
read. The local implementation is the default in SAMPLE_MODE; the Meterless
adapter mirrors every mutation to the engine's case state endpoint when
WORLD_MODEL_URL is configured.

The engine's exact REST shape must be confirmed against the participant setup
guide. The case state payload is deliberately a plain snapshot so it can be
accepted by any JSON state endpoint.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from .config import Settings
from .trace import Tracer


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class WorldModel:
    """Interface shared by the local store and the Meterless adapter."""

    engine = "local"

    def reset(self, case_id: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def add_line(self, line: dict[str, Any]) -> str:  # pragma: no cover
        raise NotImplementedError

    def update_line(self, line_id: str, **fields: Any) -> dict[str, Any]:  # pragma: no cover
        raise NotImplementedError

    def remove_line(self, line_id: str, reason: str) -> dict[str, Any]:  # pragma: no cover
        raise NotImplementedError

    def lines(self) -> list[dict[str, Any]]:  # pragma: no cover
        raise NotImplementedError


class LocalWorldModel(WorldModel):
    engine = "local-world-model"

    def __init__(self, tracer: Tracer | None = None) -> None:
        self.tracer = tracer
        self.case_id = ""
        self._lines: list[dict[str, Any]] = []
        self._removed: list[dict[str, Any]] = []
        self._conflicts: list[dict[str, Any]] = []
        self._exclusions: list[dict[str, Any]] = []
        self._claim: dict[str, Any] = {}
        self._line_counter = 0
        self._conflict_counter = 0

    def reset(self, case_id: str) -> None:
        self.case_id = case_id
        self._lines.clear()
        self._removed.clear()
        self._conflicts.clear()
        self._exclusions.clear()
        self._claim.clear()
        self._line_counter = 0
        self._conflict_counter = 0

    # -- lines ---------------------------------------------------------
    def add_line(self, line: dict[str, Any]) -> str:
        line = dict(line)
        self._line_counter += 1
        line_id = line.get("line_id") or f"L{self._line_counter:04d}"
        line["line_id"] = line_id
        line.setdefault("corroborating_sources", [])
        line.setdefault("components", [])
        line.setdefault("notes", "")
        self._lines.append(line)
        if self.tracer:
            self.tracer.event(
                "world_model_write",
                agent="reconciler",
                decision=f"line {line_id} {line.get('verification_status')}",
                line_id=line_id,
                source_table=line.get("source_table"),
                amount_aud=line.get("amount_aud"),
            )
        return line_id

    def update_line(self, line_id: str, **fields: Any) -> dict[str, Any]:
        agent = fields.pop("_agent", "system")
        for line in self._lines:
            if line["line_id"] == line_id:
                line.update(fields)
                if self.tracer:
                    self.tracer.event(
                        "world_model_update",
                        agent=agent,
                        decision=f"line {line_id} updated",
                        line_id=line_id,
                        changed=sorted(fields),
                    )
                return line
        raise KeyError(f"unknown line {line_id}")

    def remove_line(self, line_id: str, reason: str) -> dict[str, Any]:
        for index, line in enumerate(self._lines):
            if line["line_id"] == line_id:
                removed = self._lines.pop(index)
                removed["removal_reason"] = reason
                removed["removed_at"] = _now()
                self._removed.append(removed)
                if self.tracer:
                    self.tracer.event(
                        "world_model_remove",
                        agent="reconciler",
                        decision=f"line {line_id} removed: {reason}",
                        line_id=line_id,
                    )
                return removed
        raise KeyError(f"unknown line {line_id}")

    def lines(self) -> list[dict[str, Any]]:
        return list(self._lines)

    def removed_lines(self) -> list[dict[str, Any]]:
        return list(self._removed)

    def find_line(self, line_id: str) -> dict[str, Any]:
        for line in self._lines:
            if line["line_id"] == line_id:
                return line
        raise KeyError(line_id)

    def lines_for_source(self, source_table: str) -> list[dict[str, Any]]:
        return [line for line in self._lines if line.get("source_table") == source_table]

    def lines_by_reference(self, reference: str) -> list[dict[str, Any]]:
        return [line for line in self._lines if line.get("reference") == reference]

    # -- conflicts -----------------------------------------------------
    def add_conflict(self, conflict: dict[str, Any]) -> str:
        self._conflict_counter += 1
        conflict = dict(conflict)
        conflict_id = conflict.get("conflict_id") or f"CF-{self._conflict_counter:03d}"
        conflict["conflict_id"] = conflict_id
        conflict.setdefault("status", "open")
        self._conflicts.append(conflict)
        return conflict_id

    def conflicts(self) -> list[dict[str, Any]]:
        return list(self._conflicts)

    def update_conflict(self, conflict_id: str, **fields: Any) -> dict[str, Any]:
        agent = fields.pop("_agent", "system")
        for conflict in self._conflicts:
            if conflict["conflict_id"] == conflict_id:
                conflict.update(fields)
                if self.tracer:
                    self.tracer.event(
                        "conflict_update",
                        agent=agent,
                        decision=f"{conflict_id} -> {conflict.get('status')}",
                        conflict_id=conflict_id,
                        kind=conflict.get("kind"),
                    )
                return conflict
        raise KeyError(f"unknown conflict {conflict_id}")

    def add_exclusion(self, item: dict[str, Any], reason: str) -> None:
        record = dict(item)
        record["reason"] = reason
        record["excluded_at"] = _now()
        self._exclusions.append(record)
        if self.tracer:
            self.tracer.event(
                "exclusion",
                agent="reconciler",
                decision=reason,
                source_table=record.get("source_table"),
                amount_aud=record.get("amount_aud"),
            )

    def exclusions(self) -> list[dict[str, Any]]:
        return list(self._exclusions)

    # -- claim ---------------------------------------------------------
    def set_claim(self, claim: dict[str, Any]) -> None:
        self._claim = dict(claim)

    def claim(self) -> dict[str, Any]:
        return dict(self._claim)

    # -- snapshot ------------------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "lines": copy.deepcopy(self._lines),
            "removed_lines": copy.deepcopy(self._removed),
            "conflicts": copy.deepcopy(self._conflicts),
            "exclusions": copy.deepcopy(self._exclusions),
            "claim": copy.deepcopy(self._claim),
        }


class MeterlessWorldModel(LocalWorldModel):
    """Meterless Engine adapter: local ledger + mirrored case state.

    Every mutation posts the whole case snapshot to
    {WORLD_MODEL_URL}/v1/cases/{case_id}/state. Missing endpoint details are
    the only unknown; the payload is intentionally generic JSON.
    """

    engine = "meterless-world-model"

    def __init__(self, settings: Settings, tracer: Tracer | None = None) -> None:
        super().__init__(tracer)
        self.settings = settings
        self.sync_path = "/v1/cases/{case_id}/state"

    def _sync(self) -> None:
        if not self.settings.world_model_url:
            return
        try:
            import httpx

            url = self.settings.world_model_url + self.sync_path.format(case_id=self.case_id)
            headers = {"Content-Type": "application/json"}
            if self.settings.world_model_api_key:
                headers["Authorization"] = f"Bearer {self.settings.world_model_api_key}"
            with httpx.Client(timeout=15.0) as client:
                client.post(url, json=self.snapshot(), headers=headers)
        except Exception as exc:  # pragma: no cover - live only
            if self.tracer:
                self.tracer.event("engine_warning", agent="reconciler", decision=f"world model sync failed: {exc}")

    def add_line(self, line: dict[str, Any]) -> str:
        line_id = super().add_line(line)
        self._sync()
        return line_id

    def update_line(self, line_id: str, **fields: Any) -> dict[str, Any]:
        result = super().update_line(line_id, **fields)
        self._sync()
        return result

    def remove_line(self, line_id: str, reason: str) -> dict[str, Any]:
        result = super().remove_line(line_id, reason)
        self._sync()
        return result


def make_world_model(settings: Settings, tracer: Tracer | None, case_id: str) -> WorldModel:
    if not settings.offline and settings.world_model_url:
        model: WorldModel = MeterlessWorldModel(settings, tracer)
    else:
        model = LocalWorldModel(tracer)
    model.reset(case_id)
    return model
