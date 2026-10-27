#!/usr/bin/env python3
"""Build data/fixtures/sample.db from OVERTURN's source files.

The SQLite mirror uses the same table and view names as
scripts/register_zetaris_sources.sql so the same read-only queries run in both
modes.

Run: python scripts/build_sample_db.py
"""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data" / "sources"
FIXTURES = ROOT / "data" / "fixtures"
DB = FIXTURES / "sample.db"

SCHEMA = """
DROP VIEW IF EXISTS appeal_evidence;
DROP VIEW IF EXISTS claim_facts;
DROP TABLE IF EXISTS policy_clauses;
DROP TABLE IF EXISTS denial_reasons;
DROP TABLE IF EXISTS medical_records;
DROP TABLE IF EXISTS eob;
DROP TABLE IF EXISTS procedure_codes;
DROP TABLE IF EXISTS claim_documents;
DROP TABLE IF EXISTS icd10_codes;

CREATE TABLE policy_clauses (
  clause_id TEXT PRIMARY KEY, section TEXT NOT NULL, title TEXT NOT NULL,
  text TEXT NOT NULL, effective_date TEXT NOT NULL, version TEXT NOT NULL,
  applies_to TEXT NOT NULL
);
CREATE TABLE denial_reasons (
  reason_id TEXT PRIMARY KEY, reason_text TEXT NOT NULL, cited_clause TEXT NOT NULL,
  cited_code TEXT NOT NULL, cited_diagnosis TEXT NOT NULL, denial_date TEXT NOT NULL,
  reviewer TEXT NOT NULL, appeal_deadline TEXT NOT NULL
);
CREATE TABLE medical_records (
  record_id TEXT PRIMARY KEY, record_date TEXT NOT NULL, record_type TEXT NOT NULL,
  provider TEXT NOT NULL, summary TEXT NOT NULL, diagnosis_code TEXT,
  procedure_code TEXT, weeks_of_therapy INTEGER NOT NULL, notes TEXT
);
CREATE TABLE eob (
  eob_id TEXT PRIMARY KEY, claim_id TEXT NOT NULL, service_date TEXT NOT NULL,
  procedure_code TEXT NOT NULL, billed_amount REAL NOT NULL, allowed_amount REAL NOT NULL,
  paid_amount REAL NOT NULL, patient_responsibility REAL NOT NULL,
  denial_code TEXT NOT NULL, denial_date TEXT NOT NULL
);
CREATE TABLE procedure_codes (
  code TEXT PRIMARY KEY, description TEXT NOT NULL, contrast TEXT NOT NULL,
  prior_auth_required INTEGER NOT NULL, covered INTEGER NOT NULL, notes TEXT
);
CREATE TABLE claim_documents (
  document_id TEXT PRIMARY KEY, claim_id TEXT NOT NULL, name TEXT NOT NULL,
  required_by TEXT NOT NULL, status TEXT NOT NULL, source TEXT, document_date TEXT,
  requested_date TEXT, note TEXT
);
CREATE TABLE icd10_codes (
  code TEXT PRIMARY KEY, description TEXT NOT NULL, category TEXT, source TEXT
);

CREATE VIEW appeal_evidence AS
SELECT d.reason_id, d.reason_text, d.cited_clause, d.cited_code, d.cited_diagnosis,
       d.denial_date, d.appeal_deadline,
       p.clause_id, p.title AS clause_title, p.text AS clause_text, p.applies_to,
       c.description AS code_description, c.prior_auth_required, c.covered,
       i.description AS diagnosis_description
FROM denial_reasons d
LEFT JOIN policy_clauses p ON p.clause_id = d.cited_clause
LEFT JOIN procedure_codes c ON c.code = d.cited_code
LEFT JOIN icd10_codes i ON i.code = d.cited_diagnosis;

CREATE VIEW claim_facts AS
SELECT
  (SELECT MAX(weeks_of_therapy) FROM medical_records) AS max_weeks_of_therapy,
  (SELECT COUNT(*) FROM medical_records WHERE record_type = 'Physiotherapy') AS physiotherapy_sessions,
  (SELECT procedure_code FROM medical_records WHERE procedure_code IS NOT NULL
     ORDER BY record_date DESC LIMIT 1) AS ordered_procedure_code,
  (SELECT diagnosis_code FROM medical_records ORDER BY record_date DESC LIMIT 1) AS recorded_diagnosis_code,
  (SELECT COUNT(*) FROM claim_documents WHERE status = 'missing') AS missing_documents;
"""


def load_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()
    conn = sqlite3.connect(DB)
    conn.executescript(SCHEMA)

    policy = load_csv(SOURCES / "policy_clauses.csv")
    conn.executemany(
        "INSERT INTO policy_clauses VALUES (?,?,?,?,?,?,?)",
        [(r["clause_id"], r["section"], r["title"], r["text"],
          r["effective_date"], r["version"], r["applies_to"]) for r in policy],
    )

    denial = load_csv(SOURCES / "denial_reasons.csv")
    conn.executemany(
        "INSERT INTO denial_reasons VALUES (?,?,?,?,?,?,?,?)",
        [(r["reason_id"], r["reason_text"], r["cited_clause"], r["cited_code"],
          r["cited_diagnosis"], r["denial_date"], r["reviewer"], r["appeal_deadline"])
         for r in denial],
    )

    records = load_csv(SOURCES / "medical_records.csv")
    conn.executemany(
        "INSERT INTO medical_records VALUES (?,?,?,?,?,?,?,?,?)",
        [(r["record_id"], r["record_date"], r["record_type"], r["provider"],
          r["summary"], r["diagnosis_code"] or None, r["procedure_code"] or None,
          int(r["weeks_of_therapy"]), r["notes"]) for r in records],
    )

    eob = load_csv(SOURCES / "eob.csv")
    conn.executemany(
        "INSERT INTO eob VALUES (?,?,?,?,?,?,?,?,?,?)",
        [(r["eob_id"], r["claim_id"], r["service_date"], r["procedure_code"],
          float(r["billed_amount"]), float(r["allowed_amount"]), float(r["paid_amount"]),
          float(r["patient_responsibility"]), r["denial_code"], r["denial_date"]) for r in eob],
    )

    codes = load_csv(SOURCES / "procedure_codes.csv")
    conn.executemany(
        "INSERT INTO procedure_codes VALUES (?,?,?,?,?,?)",
        [(r["code"], r["description"], r["contrast"], int(r["prior_auth_required"]),
          int(r["covered"]), r["notes"]) for r in codes],
    )

    documents = json.loads((SOURCES / "claim_documents.json").read_text(encoding="utf-8"))
    conn.executemany(
        "INSERT INTO claim_documents VALUES (?,?,?,?,?,?,?,?,?)",
        [(d["document_id"], documents["claim_id"], d["name"], d["required_by"],
          d["status"], d.get("source") or None, d.get("document_date") or None,
          d.get("requested_date") or None, d.get("note") or None) for d in documents["documents"]],
    )

    icd10 = json.loads((SOURCES / "icd10_codes.json").read_text(encoding="utf-8"))
    conn.executemany(
        "INSERT INTO icd10_codes VALUES (?,?,?,?)",
        [(row["code"], row["description"], row.get("category"), row.get("source")) for row in icd10],
    )

    conn.commit()
    counts = {
        table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("policy_clauses", "denial_reasons", "medical_records", "eob",
                      "procedure_codes", "claim_documents", "icd10_codes", "appeal_evidence")
    }
    conn.close()
    print(f"built {DB}")
    for table, count in counts.items():
        print(f"  {table}: {count}")


if __name__ == "__main__":
    main()
