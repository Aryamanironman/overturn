"""Both loops terminate at their caps and escalation asks exactly one question."""

from __future__ import annotations

from overturn.llm import LLMClient
from overturn.reconciler import Reconciler
from overturn.run import MAX_ADVOCATE_ITERS, MAX_CONFLICT_ITERS, run_adversarial_loop, run_conflict_loop
from overturn.trace import Tracer
from overturn.world_model import LocalWorldModel
from overturn.zetaris import SqlClient

CASE = {
    "case_id": "loop-test",
    "as_of": "2026-10-24",
    "claimant": {"name": "Test"},
    "insurer": "Test Insurer",
    "claim_id": "CLM-TEST",
    "request": "appeal a denied claim",
}


class AlwaysConflictCritic:
    def __init__(self) -> None:
        self.calls = 0

    def conflict_check(self, world, iteration):
        self.calls += 1
        if not any(
            item.get("kind") == "denial_reason" and item.get("status") == "open"
            for item in world.conflicts()
        ):
            world.add_conflict({
                "kind": "denial_reason",
                "key": f"fake-{self.calls}",
                "status": "open",
                "reason_id": f"FAKE-{self.calls}",
                "requery_sql": "SELECT * FROM claim_documents WHERE document_id = 'DOC-003'",
                "action": {"type": "mark_conditional"},
                "line_ids": [],
                "question": "Does this reason survive the loop cap test?",
            })
        return {"findings": []}


class AlwaysBreak:
    def _result(self):
        return {
            "attacks": [{"claim": "fake attack", "evidence": {}, "severity": "high"}],
            "breaks_claim": True,
            "requery": {
                "sql": "SELECT 1",
                "action": {"type": "verify_diagnosis"},
                "why": "loop cap test",
            },
        }

    def adversarial_review(self, world, claim, iteration):
        return self._result()

    def review(self, world, claim, iteration):
        return self._result()


def _world(tracer):
    world = LocalWorldModel(tracer)
    world.reset("loop-test")
    world.set_claim({"conditional": False, "diagnosis_verified": False})
    return world


def test_conflict_loop_caps_and_escalates_once(tmp_path, base_settings):
    tracer = Tracer(tmp_path / "trace.jsonl")
    world = _world(tracer)
    sql = SqlClient(base_settings, tracer)
    llm = LLMClient(base_settings, tracer)
    reconciler = Reconciler(sql, llm, tracer)
    critic = AlwaysConflictCritic()

    stats = run_conflict_loop(world, critic, reconciler, CASE, base_settings, tracer)

    assert stats["iterations"] <= MAX_CONFLICT_ITERS + 1
    assert stats["escalations"] == 1
    assert stats["requeries"] <= MAX_CONFLICT_ITERS + 1
    assert critic.calls <= MAX_CONFLICT_ITERS + 2
    assert len([event for event in tracer.events if event["step"] == "escalation"]) == 1
    assert any(event["step"] == "loop_cap" for event in tracer.events)
    assert any(event["step"] == "requery_exec" for event in tracer.events)


def test_adversarial_loop_caps(tmp_path, base_settings):
    tracer = Tracer(tmp_path / "trace.jsonl")
    world = _world(tracer)
    sql = SqlClient(base_settings, tracer)
    llm = LLMClient(base_settings, tracer)
    reconciler = Reconciler(sql, llm, tracer)

    stats = run_adversarial_loop(world, AlwaysBreak(), AlwaysBreak(), reconciler, CASE, tracer)

    assert stats["requeries"] <= MAX_ADVOCATE_ITERS
    assert stats["iterations"] <= MAX_ADVOCATE_ITERS
    assert any(
        event["step"] == "loop_cap" and "advocate" in event.get("decision", "")
        for event in tracer.events
    )
