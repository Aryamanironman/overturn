"""The Zetaris USL and data-quality views return the expected case facts.

The SQL is read from the shipped registration script so the test fails if the
script and the semantic layer drift apart. SQLite can execute the view bodies
because SAMPLE_MODE mirrors the same seven tables and the two base views.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "register_zetaris_sources.sql"
DB = ROOT / "data" / "fixtures" / "sample.db"


def _view_sql(name: str) -> str:
    text = SCRIPT.read_text(encoding="utf-8")
    match = re.search(
        rf"CREATE SCHEMASTORE VIEW {name} WITH CONTAINER overturn AS(.*?);",
        text,
        re.DOTALL,
    )
    if not match:
        raise AssertionError(f"view {name} not found in {SCRIPT.name}")
    return match.group(1)


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    for name in ("usl_claim_review", "dq_claim_integrity"):
        con.execute(f"CREATE TEMP VIEW {name} AS {_view_sql(name)}")
    return con


def test_usl_and_data_quality_views() -> None:
    con = _connect()
    try:
        rows = con.execute(
            "SELECT * FROM usl_claim_review ORDER BY reason_id"
        ).fetchall()
        assert len(rows) == 4
        by_id = {row["reason_id"]: row for row in rows}

        den02 = by_id["DEN-02"]
        assert den02["cited_code"] == "MRI-LS-002"
        assert den02["ordered_procedure_code"] == "MRI-LS-001"
        assert den02["recorded_diagnosis_code"] == "M54.5"
        assert den02["cited_diagnosis"] == "M51.1"
        assert "contrast" in den02["code_description"].lower()

        den03 = by_id["DEN-03"]
        assert den03["physiotherapy_sessions"] == 12
        assert den03["max_weeks_of_therapy"] == 12

        assert all(row["missing_documents"] == 1 for row in rows)
        assert all(row["first_missing_document"] == "DOC-003" for row in rows)
        assert "spinal fusion" in by_id["DEN-01"]["clause_text"].lower()

        dq = con.execute(
            "SELECT * FROM dq_claim_integrity ORDER BY rule_id"
        ).fetchall()
        assert len(dq) == 5
        assert [row["rule_id"] for row in dq] == [
            "DQ-01", "DQ-02", "DQ-03", "DQ-04", "DQ-05",
        ]
        assert all(row["failures"] == 0 and row["status"] == "pass" for row in dq)
    finally:
        con.close()
