"""Meterless Nightshift client and model routing.

Nightshift is the product's primary AI provider. The runtime contract:
  Authorization: Bearer <Runtime token>
  meterless-app: <app name>
  meterless-scope: user
  GET  /v1/models
  POST /v1/chat/completions

Every request logs the requested model and the model actually served.
Critic and Advocate are pinned to the Nemotron lane when NEMOTRON_MODEL is set.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable

from .config import Settings
from .trace import Tracer, digest

JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)
MODEL_ALIASES = {"", "auto", "meterless/auto", "unset"}


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, settings: Settings, tracer: Tracer, fixtures_path: Path | None = None) -> None:
        self.settings = settings
        self.tracer = tracer
        self.fixtures_path = fixtures_path
        self.fixtures = self._load_fixtures() if fixtures_path else {}
        self._models: list[str] | None = None

    def _load_fixtures(self) -> dict[str, dict[str, Any]]:
        fixtures: dict[str, dict[str, Any]] = {}
        if not self.fixtures_path or not self.fixtures_path.exists():
            return fixtures
        for line in self.fixtures_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = record.get("key")
            if key:
                fixtures[key] = record
        return fixtures

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.settings.nightshift_api_key}",
            "meterless-app": self.settings.nightshift_app,
            "meterless-scope": self.settings.nightshift_scope,
        }
        return headers

    def available_models(self) -> list[str]:
        if self.settings.offline:
            return []
        if self._models is not None:
            return self._models
        try:
            import httpx

            with httpx.Client(timeout=self.settings.nightshift_timeout) as client:
                response = client.get(
                    self.settings.nightshift_base_url + "/models",
                    headers=self._headers(),
                )
                response.raise_for_status()
                payload = response.json()
            items = payload.get("data", payload) if isinstance(payload, dict) else payload
            models = []
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and item.get("id"):
                        models.append(str(item["id"]))
                    elif isinstance(item, str):
                        models.append(item)
            self._models = models
            self.tracer.event(
                "model_discovery",
                agent="system",
                decision=f"{len(models)} Nightshift model(s) discovered",
                models=models[:40],
            )
            return models
        except Exception as exc:  # pragma: no cover - live only
            self.tracer.event("model_discovery", agent="system", decision=f"discovery failed: {exc}")
            self._models = []
            return []

    def model_for(self, agent: str) -> str:
        return self.settings.models.get(agent, "")

    def resolve_model(self, agent: str) -> str:
        requested = self.model_for(agent) or "meterless/auto"
        if agent in {"critic", "advocate"} and self.settings.models.get("nemotron"):
            return self.settings.models["nemotron"]
        if requested.lower() in MODEL_ALIASES:
            models = self.available_models()
            if models:
                if agent in {"critic", "advocate"}:
                    nemotron = [model for model in models if "nemotron" in model.lower()]
                    if nemotron:
                        return nemotron[0]
                return models[0]
            return "meterless/auto"
        return requested

    def routing_table(self) -> dict[str, str]:
        if self.settings.offline:
            return {
                "planner": "offline-deterministic",
                "reconciler": "offline-deterministic",
                "critic": "offline-deterministic",
                "advocate": "offline-deterministic",
                "reporter": "offline-deterministic",
            }
        return {
            "planner": self.model_for("planner") or "meterless/auto",
            "reconciler": self.model_for("reconciler") or "meterless/auto",
            "critic": self.model_for("critic") or "meterless/auto",
            "advocate": self.model_for("advocate") or "meterless/auto",
            "reporter": self.model_for("reporter") or "meterless/auto",
        }

    def complete(
        self,
        *,
        agent: str,
        kind: str,
        messages: list[dict[str, str]],
        offline_fn: Callable[[], dict[str, Any]],
        iteration: int = 0,
    ) -> dict[str, Any]:
        key = f"{agent}|{kind}|{iteration}"
        input_digest = digest({"agent": agent, "kind": kind, "messages": messages})
        started = time.perf_counter()
        requested_model = self.model_for(agent)
        served_model = requested_model

        if not self.settings.offline and key in self.fixtures:
            record = self.fixtures[key]
            content = record.get("content", {})
            served_model = record.get("model", requested_model or "replay")
            mode = "replay"
        elif not self.settings.offline:
            content, requested_model, served_model = self._call_live(agent, messages)
            mode = "live"
        else:
            content = offline_fn()
            requested_model = "offline-deterministic"
            served_model = "offline-deterministic"
            mode = "offline"

        latency_ms = int((time.perf_counter() - started) * 1000)
        if not isinstance(content, dict):
            raise LLMError(f"{agent}/{kind} returned {type(content).__name__}, expected an object")
        self.tracer.event(
            "agent_call",
            agent=agent,
            mode=mode,
            model=served_model,
            requested_model=requested_model,
            input_digest=input_digest,
            latency_ms=latency_ms,
            decision=f"{kind}: {','.join(sorted(content.keys())[:6])}",
            iteration=iteration,
        )
        return content

    def _call_live(
        self, agent: str, messages: list[dict[str, str]]
    ) -> tuple[dict[str, Any], str, str]:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover
            raise LLMError("httpx is required for live Nightshift calls") from exc

        if not self.settings.nightshift_base_url or not self.settings.nightshift_api_key:
            raise LLMError("Nightshift URL/token missing; set METERLESS_BASE_URL and METERLESS_RUNTIME_TOKEN")

        model = self.resolve_model(agent)
        url = self.settings.nightshift_base_url.rstrip("/") + "/chat/completions"
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                with httpx.Client(timeout=self.settings.nightshift_timeout) as client:
                    response = client.post(url, json=payload, headers=self._headers())
                    if response.status_code == 400 and "response_format" in payload:
                        payload.pop("response_format", None)
                        continue
                    if response.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                        last_error = LLMError(f"HTTP {response.status_code}")
                        time.sleep(0.8 * (attempt + 1))
                        continue
                    response.raise_for_status()
                    data = response.json()
                served = str(data.get("model") or model) if isinstance(data, dict) else model
                try:
                    raw = data["choices"][0]["message"]["content"]
                except (KeyError, IndexError, TypeError) as exc:
                    raise LLMError("Nightshift response did not contain choices[0].message.content") from exc
                return self._parse_json(raw), model, served
            except Exception as exc:  # pragma: no cover
                last_error = exc
                if attempt < 2:
                    time.sleep(0.8 * (attempt + 1))
        raise LLMError(f"Nightshift call failed for {agent}/{model}: {last_error}") from last_error

    @staticmethod
    def _parse_json(raw: Any) -> dict[str, Any]:
        if isinstance(raw, list):
            raw = "".join(
                part.get("text", "") for part in raw if isinstance(part, dict)
            )
        if not isinstance(raw, str):
            raise LLMError("model content was not a string")
        cleaned = JSON_FENCE.sub("", raw.strip())
        try:
            value = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise LLMError(f"model did not return valid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise LLMError("model returned JSON that is not an object")
        return value
