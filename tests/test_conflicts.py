"""The four planted denial conflicts must end in the documented states."""

from __future__ import annotations


def test_reasons_end_in_expected_states(pipeline):
    packet = pipeline["packet"]
    reasons = {item["reason_id"]: item for item in packet["denial_reasons"]}
    assert set(reasons) == {"DEN-01", "DEN-02", "DEN-03", "DEN-04"}
    assert reasons["DEN-01"]["status"] == "rebutted"
    assert reasons["DEN-02"]["status"] == "rebutted"
    assert reasons["DEN-03"]["status"] == "rebutted"
    assert reasons["DEN-04"]["status"] == "missing"


def test_wrong_clause_cites_the_right_policy(pipeline):
    reason = next(item for item in pipeline["packet"]["denial_reasons"] if item["reason_id"] == "DEN-01")
    sources = {citation["source"] for citation in reason["citations"]}
    assert "policy_clauses:POL-4.3" in sources
    assert "policy_clauses:POL-4.1" in sources
    assert "does not apply to diagnostic MRI" in reason["rebuttal"]


def test_code_and_diagnosis_mismatch(pipeline):
    reason = next(item for item in pipeline["packet"]["denial_reasons"] if item["reason_id"] == "DEN-02")
    sources = {citation["source"] for citation in reason["citations"]}
    assert "procedure_codes:MRI-LS-002" in sources
    assert "procedure_codes:MRI-LS-001" in sources
    assert "icd10_codes:M51.1" in sources
    assert "icd10_codes:M54.5" in sources
    assert pipeline["packet"]["claim"]["procedure_code"] == "MRI-LS-001"
    assert pipeline["packet"]["claim"]["diagnosis_code"] == "M54.5"
    assert pipeline["packet"]["claim"]["diagnosis_verified"] is True


def test_conservative_treatment_is_documented(pipeline):
    reason = next(item for item in pipeline["packet"]["denial_reasons"] if item["reason_id"] == "DEN-03")
    sources = {citation["source"] for citation in reason["citations"]}
    physio = [
        citation for citation in reason["citations"]
        if "session" in (citation.get("summary") or "").lower()
    ]
    assert len(physio) == 12
    assert "medical_records:REC-002" in sources
    assert "12 physiotherapy sessions over 12 weeks" in reason["rebuttal"]


def test_missing_letter_is_never_fabricated(pipeline):
    packet = pipeline["packet"]
    reason = next(item for item in packet["denial_reasons"] if item["reason_id"] == "DEN-04")
    sources = {citation["source"] for citation in reason["citations"]}
    assert "claim_documents:DOC-003" in sources
    assert "policy_clauses:POL-6.4" in sources
    assert packet["missing_documents"][0]["document_id"] == "DOC-003"
    assert "not been fabricated" in packet["cover_letter"]
    for rebuttal in packet["rebuttals"]:
        if rebuttal["reason_id"] == "DEN-04":
            assert "not been fabricated" in rebuttal["text"]
    assert "Specialist referral letter" in packet["appeal_strength"]["next_best_action"]


def test_score_and_cap(pipeline):
    strength = pipeline["packet"]["appeal_strength"]
    assert strength["score"] == 84
    assert strength["raw_score"] == 90
    assert strength["cap"] == 84
    assert strength["bucket"] == "solid"
    assert strength["status"] == "conditional"
    assert strength["counts"]["rebutted"] == 3
    assert strength["counts"]["missing"] == 1
    assert strength["projected_score_with_missing_fixed"] == 100


def test_trace_shows_real_requeries(pipeline):
    events = pipeline["trace"]
    requeries = [event for event in events if event["step"] == "requery_exec"]
    assert len(requeries) == 5
    decisions = " ".join(event.get("decision", "") for event in requeries)
    assert "mark_missing" in decisions
    assert "verify_diagnosis" in decisions
    assert any(event["step"] == "adversarial_review" for event in events)
    assert any(event["step"] == "advocate_review" for event in events)


def test_counterfactuals_are_meaningful(pipeline):
    results = {item["removed_source"]: item for item in pipeline["packet"]["counterfactuals"]}
    for source in ("policy_clauses", "medical_records", "procedure_codes", "icd10_codes"):
        assert results[source]["score_delta"] < 0
    assert results["eob"]["score_delta"] == 0
