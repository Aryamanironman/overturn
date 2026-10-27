"""Live Nightshift smoke test for the two Nemotron-pinned agents."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from overturn.config import Settings  # noqa: E402
from overturn.llm import LLMClient  # noqa: E402
from overturn.prompts import advocate_messages, critic_conflict_messages  # noqa: E402
from overturn.trace import Tracer  # noqa: E402


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def main() -> None:
    env = read_env(ROOT / ".env")
    model = env.get("NEMOTRON_MODEL", "nvidia/nemotron-3-ultra-550b-a55b")
    token = env.get("METERLESS_RUNTIME_TOKEN", "")
    if not token:
        raise SystemExit("METERLESS_RUNTIME_TOKEN missing from .env")

    settings = Settings(
        offline=False,
        sample_mode_raw="false",
        nightshift_base_url=env.get("METERLESS_BASE_URL", "http://127.0.0.1:8088/v1"),
        nightshift_api_key=token,
        nightshift_app=env.get("METERLESS_APP", "overturn"),
        nightshift_scope=env.get("METERLESS_SCOPE", "user"),
        models={
            "planner": model,
            "reconciler": model,
            "critic": model,
            "advocate": model,
            "reporter": model,
            "nemotron": model,
        },
    )
    packet = json.loads((ROOT / "out" / "appeal_packet.json").read_text(encoding="utf-8"))
    reasons = packet["denial_reasons"]
    findings = [
        {
            "reason_id": reason["reason_id"],
            "reason_text": reason["reason_text"],
            "status": reason["status"],
            "finding_kind": reason["finding_kind"],
            "rebuttal": reason["rebuttal"],
            "citations": reason.get("citations", []),
        }
        for reason in reasons
    ]
    summary = {"score": packet["appeal_strength"]["score"], **packet["appeal_strength"]["counts"]}

    tracer = Tracer(ROOT / "out" / "nightshift_smoke_trace.jsonl")
    client = LLMClient(settings, tracer)

    critic = client.complete(
        agent="critic",
        kind="conflict_check",
        messages=critic_conflict_messages(findings, summary),
        offline_fn=lambda: {},
    )
    advocate = client.complete(
        agent="advocate",
        kind="adversarial_review",
        messages=advocate_messages(packet["claim"], summary),
        offline_fn=lambda: {},
    )

    (ROOT / "out" / "nightshift_smoke.json").write_text(
        json.dumps({"critic": critic, "advocate": advocate}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    for event in tracer.events:
        if event.get("step") == "agent_call":
            print(
                f"{event['agent']:9s} mode={event['mode']:5s} "
                f"model={event['model']} latency={event['latency_ms']}ms"
            )
    print("critic keys:", sorted(critic))
    print("advocate keys:", sorted(advocate))
    print("wrote out/nightshift_smoke.json and out/nightshift_smoke_trace.jsonl")


if __name__ == "__main__":
    main()
