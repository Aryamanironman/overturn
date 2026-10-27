"""The planted data must contain the four conflicts exactly as documented."""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data" / "sources"


def read_csv(name):
    with (SOURCES / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_row_counts():
    assert len(read_csv("policy_clauses.csv")) == 12
    assert len(read_csv("denial_reasons.csv")) == 4
    assert len(read_csv("medical_records.csv")) == 20
    assert len(read_csv("eob.csv")) == 1
    assert len(read_csv("procedure_codes.csv")) == 6


def test_wrong_clause_material():
    policy = {row["clause_id"]: row for row in read_csv("policy_clauses.csv")}
    assert "does not apply to diagnostic MRI" in policy["POL-4.3"]["text"]
    assert policy["POL-4.3"]["applies_to"] == "SPINE-FUSION-001"


def test_code_and_diagnosis_conflict():
    denial = {row["reason_id"]: row for row in read_csv("denial_reasons.csv")}
    assert denial["DEN-02"]["cited_code"] == "MRI-LS-002"
    assert denial["DEN-02"]["cited_diagnosis"] == "M51.1"
    eob = read_csv("eob.csv")[0]
    assert eob["procedure_code"] == "MRI-LS-001"


def test_twelve_weeks_of_therapy():
    records = read_csv("medical_records.csv")
    physio = [row for row in records if row["record_type"] == "Physiotherapy"]
    assert len(physio) == 12
    assert max(int(row["weeks_of_therapy"]) for row in physio) == 12


def test_missing_letter_is_missing():
    documents = json.loads((SOURCES / "claim_documents.json").read_text(encoding="utf-8"))
    missing = [doc for doc in documents["documents"] if doc["status"] == "missing"]
    assert [doc["document_id"] for doc in missing] == ["DOC-003"]
    assert "fabricate" in missing[0]["note"].lower()


def test_primary_code_does_not_require_prior_auth():
    codes = {row["code"]: row for row in read_csv("procedure_codes.csv")}
    assert codes["MRI-LS-001"]["prior_auth_required"] == "0"
    assert codes["MRI-LS-002"]["prior_auth_required"] == "1"
