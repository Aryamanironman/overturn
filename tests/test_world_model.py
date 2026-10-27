"""The Critic must read the same evidence ledger the Reconciler wrote."""

from __future__ import annotations

from overturn.critic import Critic
from overturn.llm import LLMClient
from overturn.planner import default_plan
from overturn.reconciler import Reconciler
from overturn.router import route_request
from overturn.trace import Tracer
from overturn.world_model import LocalWorldModel
from overturn.zetaris import SqlClient


def test_critic_sees_reconciler_write(tmp_path, base_settings, case):
    tracer = Tracer(tmp_path / "trace.jsonl")
    world = LocalWorldModel(tracer)
    world.reset(case["case_id"])
    sql = SqlClient(base_settings, tracer)
    llm = LLMClient(base_settings, tracer)
    reconciler = Reconciler(sql, llm, tracer)
    policy = route_request(case["request"], case["purpose"])
    reconciler.reconcile(world, default_plan(policy), case)

    written = {line["line_id"] for line in world.lines()}
    assert len(written) == 47  # 12 policy + 20 records + 1 EOB + 6 codes + 3 ICD-10 + 5 docs

    critic = Critic(llm, tracer)
    result = critic.conflict_check(world, iteration=0)
    assert len(result["findings"]) == 4
    assert {finding["kind"] for finding in result["findings"]} == {
        "wrong_clause", "code_mismatch", "medical_necessity", "missing_document"
    }

    for finding in result["findings"]:
        assert set(finding["citations"]) <= written
        for line_id in finding["citations"]:
            assert world.find_line(line_id)["line_id"] == line_id

    missing = next(
        line for line in world.lines()
        if line["source_table"] == "claim_documents" and line["source_row_id"] == "DOC-003"
    )
    assert missing["verification_status"] == "missing"

    denied = next(conflict for conflict in world.conflicts() if conflict["reason_id"] == "DEN-01")
    assert denied["action"]["type"] == "rebut_reason"
    assert "POL-4.3" in denied["requery_sql"]

    # A write made after the Critic's read is visible to the next read.
    first = world.lines()[0]
    world.update_line(first["line_id"], notes="updated after first read")
    assert world.find_line(first["line_id"])["notes"] == "updated after first read"
