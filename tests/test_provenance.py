"""Tamper evidence, counterfactual coverage and computed scores."""

from __future__ import annotations

from overturn.reporter import verify_chain
from overturn.router import route_request
from overturn.scorer import score_appeal


def test_hash_chain_verifies_and_detects_tampering(pipeline):
    packet = pipeline["packet"]
    assert verify_chain(packet["evidence"], packet["provenance"]["head_hash"]) is True
    tampered = [dict(line) for line in packet["evidence"]]
    tampered[0]["summary"] = tampered[0]["summary"] + " (edited)"
    assert verify_chain(tampered, packet["provenance"]["head_hash"]) is False
    for line in packet["evidence"]:
        assert len(line["hash"]) == 64
        assert len(line["prev_hash"]) == 64


def test_counterfactuals_cover_evidence_sources(pipeline):
    packet = pipeline["packet"]
    expected = {"policy_clauses", "medical_records", "procedure_codes", "eob", "icd10_codes"}
    results = {item["removed_source"]: item for item in packet["counterfactuals"]}
    assert set(results) == expected
    for item in packet["counterfactuals"]:
        assert "score_delta" in item
        assert item["score_after"] >= 0


def test_packet_score_recomputes(pipeline, case):
    packet = pipeline["packet"]
    policy = route_request(case["request"], case["purpose"])
    recomputed = score_appeal(
        packet["denial_reasons"],
        packet["evidence"],
        packet["claim"],
        case["as_of"],
        policy,
    )
    assert recomputed["score"] == packet["appeal_strength"]["score"]
    assert recomputed["bucket"] == packet["appeal_strength"]["bucket"]
    assert recomputed["status"] == packet["appeal_strength"]["status"]


def test_missing_document_stays_missing(pipeline):
    packet = pipeline["packet"]
    missing_lines = [
        line for line in packet["evidence"]
        if line["source_table"] == "claim_documents" and line["verification_status"] == "missing"
    ]
    assert len(missing_lines) == 1
    assert missing_lines[0]["source_row_id"] == "DOC-003"
    assert "not been fabricated" in packet["cover_letter"]
