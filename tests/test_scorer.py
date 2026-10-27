"""The appeal-strength score is deterministic and hand-computable."""

from __future__ import annotations

from overturn.router import route_request
from overturn.scorer import bucket_for, counterfactuals, score_appeal

AS_OF = "2026-10-24"
POLICY = route_request("denied claim, internal appeal", "denial_appeal")


def line(line_id, source_table, date="2026-06-01", payload=None):
    return {
        "line_id": line_id,
        "source_table": source_table,
        "source_row_id": line_id,
        "date": date,
        "verification_status": "documented",
        "confidence": 0.9,
        "summary": line_id,
        "payload": payload or {},
    }


def reason(reason_id, citations, kind, status="rebutted", missing=None):
    return {
        "kind": "denial_reason",
        "reason_id": reason_id,
        "status": status,
        "citations": citations,
        "finding_kind": kind,
        "missing_document": missing,
    }


def fixture():
    lines = [
        line("P1", "policy_clauses"),
        line("P2", "policy_clauses"),
        line("C1", "procedure_codes"),
        line("C2", "procedure_codes"),
        line("R1", "medical_records"),
        line("R2", "medical_records"),
        line("I1", "icd10_codes"),
        line("I2", "icd10_codes"),
        line("E1", "eob", "2026-10-01"),
        line("DOC-003", "claim_documents", "2026-08-20",
             {"name": "Specialist referral letter", "required_by": "POL-6.4", "requested_date": "2026-08-20"}),
    ]
    conflicts = [
        reason("DEN-01", ["P1", "P2"], "wrong_clause"),
        reason("DEN-02", ["C1", "C2"], "code_mismatch"),
        reason("DEN-03", ["R1", "R2"], "medical_necessity"),
        reason("DEN-04", ["P1", "DOC-003"], "missing_document", "missing", "DOC-003"),
    ]
    claim = {"missing_documents": ["DOC-003"]}
    return lines, conflicts, claim


def test_hand_computed_score():
    lines, conflicts, claim = fixture()
    result = score_appeal(conflicts, lines, claim, AS_OF, POLICY)
    # 100 - 0 unresolved - 15 missing + 5 all-supported = 90, capped at 84.
    assert result["raw_score"] == 90
    assert result["cap"] == 84
    assert result["score"] == 84
    assert result["bucket"] == "solid"
    assert result["status"] == "conditional"
    assert result["projected_score_with_missing_fixed"] == 100
    assert result["counts"] == {
        "reason_count": 4,
        "rebutted": 3,
        "missing": 1,
        "unresolved": 0,
        "unsupported": 0,
        "stale_evidence": 0,
    }
    assert "Specialist referral letter" in result["next_best_action"]


def test_missing_document_fixed_removes_cap():
    lines, conflicts, claim = fixture()
    result = score_appeal(conflicts[:3], lines, {"missing_documents": []}, AS_OF, POLICY)
    assert result["score"] == 100
    assert result["bucket"] == "strong"
    assert result["status"] == "ready"


def test_unresolved_reason_deducts_and_breaks_bonus():
    lines, conflicts, claim = fixture()
    conflicts[2] = reason("DEN-03", [], "medical_necessity", status="open")
    result = score_appeal(conflicts, lines, claim, AS_OF, POLICY)
    assert result["raw_score"] == 65  # 100 - 20 - 15 + 0
    assert result["score"] == 65
    assert result["counts"]["unresolved"] == 1
    assert result["bonus"]["points"] == 0


def test_buckets():
    assert [bucket_for(value) for value in (90, 85, 84, 70, 69, 55, 54)] == [
        "strong", "strong", "solid", "solid", "partial", "partial", "weak"
    ]


def test_counterfactual_dependencies():
    lines, conflicts, claim = fixture()
    results = {item["removed_source"]: item for item in counterfactuals(conflicts, lines, claim, AS_OF, POLICY)}
    assert results["policy_clauses"]["score_delta"] < 0
    assert results["medical_records"]["score_delta"] < 0
    assert results["procedure_codes"]["score_delta"] < 0
    assert results["icd10_codes"]["score_delta"] < 0
    assert results["eob"]["score_delta"] == 0
    assert results["policy_clauses"]["rebutted_after"] == 2
