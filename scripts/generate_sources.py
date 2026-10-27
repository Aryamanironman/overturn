#!/usr/bin/env python3
"""Generate OVERTURN's synthetic denial-appeal sources.

Run:
    python scripts/generate_sources.py

The case is synthetic. No real patient, insurer, provider or claim is
represented. Names, member ids and domains are fictional (.invalid).

Planted conflicts (see data/CONFLICTS.md):
  C1  DEN-01 cites the experimental clause, which by its own text does not
      apply to diagnostic MRI of the lumbar spine.
  C2  DEN-02 cites the with-contrast code MRI-LS-002 while the order, EOB and
      record use MRI-LS-001 (without contrast); the denial also cites the wrong
      diagnosis code M51.1, while the record uses M54.5.
  C3  DEN-03 says no conservative treatment is documented; the record shows
      twelve weeks of physiotherapy and an NSAID trial.
  C4  DEN-04 says the specialist referral letter is missing. It is genuinely
      missing and must stay missing: the packet is conditional, not fabricated.
"""

from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "sources"
SRC.mkdir(parents=True, exist_ok=True)

AS_OF = date(2026, 10, 24)
DENIAL_DATE = date(2026, 10, 1)
APPEAL_DEADLINE = date(2026, 11, 30)
CASE_ID = "ava"
CLAIM_ID = "CLM-2026-0915"

POLICY = [
    ("POL-4.1", "4.1", "Covered imaging",
     "MRI lumbar spine without contrast (MRI-LS-001) is covered when the member has completed at least six weeks of conservative therapy.",
     "2026-01-01", "2026.1", "MRI-LS-001"),
    ("POL-4.2", "4.2", "Prior authorisation",
     "MRI lumbar spine without contrast (MRI-LS-001) does not require prior authorisation. Contrast studies (MRI-LS-002, MRI-LS-003) require prior authorisation.",
     "2026-01-01", "2026.1", "MRI-LS-001;MRI-LS-002;MRI-LS-003"),
    ("POL-4.3", "4.3", "Experimental or investigational",
     "The experimental exclusion applies to spinal fusion (SPINE-FUSION-001) and disc replacement. It does not apply to diagnostic MRI of the lumbar spine.",
     "2026-01-01", "2026.1", "SPINE-FUSION-001"),
    ("POL-5.1", "5.1", "Medical necessity",
     "Lumbar imaging is medically necessary when the clinical record documents failed conservative treatment for at least six weeks, including physiotherapy or analgesic medication.",
     "2026-01-01", "2026.1", "MRI-LS-001"),
    ("POL-5.2", "5.2", "Conservative therapy",
     "Conservative therapy includes physiotherapy, a structured home exercise programme and analgesic medication.",
     "2026-01-01", "2026.1", "all"),
    ("POL-6.4", "6.4", "Claim documentation",
     "An imaging claim must include a specialist referral letter dated after the imaging order. Without it the claim is incomplete.",
     "2026-01-01", "2026.1", "MRI-LS-001"),
    ("POL-7.2", "7.2", "Claim edits",
     "Procedure code MRI-LS-002 (MRI with contrast) requires prior authorisation. MRI-LS-001 (without contrast) does not.",
     "2026-01-01", "2026.1", "MRI-LS-002"),
    ("POL-8.1", "8.1", "Internal appeal",
     "A member may request an internal appeal within 60 days of the denial date.",
     "2026-01-01", "2026.1", "all"),
    ("POL-9.3", "9.3", "Policy version",
     "Version 2026.1 is effective 1 January 2026 and supersedes version 2025.3.",
     "2026-01-01", "2026.1", "all"),
    ("POL-10.1", "10.1", "Definitions",
     "A specialist referral letter is a letter from the treating specialist that recommends the imaging and is dated after the imaging order.",
     "2026-01-01", "2026.1", "all"),
    ("POL-12.4", "12.4", "Clinical records",
     "Clinical records must be dated and attributable to a treating provider.",
     "2026-01-01", "2026.1", "all"),
    ("POL-13.1", "13.1", "Response time",
     "The insurer must respond to an internal appeal within 30 days of receiving it.",
     "2026-01-01", "2026.1", "all"),
]

DENIAL = [
    ("DEN-01", "The service is experimental or investigational.", "POL-4.3", "MRI-LS-001", "M54.5",
     DENIAL_DATE.isoformat(), "Northbridge Health Claims Review", APPEAL_DEADLINE.isoformat()),
    ("DEN-02", "Procedure code MRI-LS-002 (MRI with contrast) is not covered without prior authorisation.",
     "POL-7.2", "MRI-LS-002", "M51.1", DENIAL_DATE.isoformat(),
     "Northbridge Health Claims Review", APPEAL_DEADLINE.isoformat()),
    ("DEN-03", "No conservative treatment is documented.", "POL-5.1", "MRI-LS-001", "M54.5",
     DENIAL_DATE.isoformat(), "Northbridge Health Claims Review", APPEAL_DEADLINE.isoformat()),
    ("DEN-04", "A specialist referral letter was not provided.", "POL-6.4", "MRI-LS-001", "M54.5",
     DENIAL_DATE.isoformat(), "Northbridge Health Claims Review", APPEAL_DEADLINE.isoformat()),
]

CODES = [
    ("MRI-LS-001", "MRI lumbar spine without contrast", "no", 0, 1,
     "Covered under POL-4.1 when conservative therapy is at least six weeks."),
    ("MRI-LS-002", "MRI lumbar spine with contrast", "yes", 1, 1,
     "Requires prior authorisation under POL-7.2."),
    ("MRI-LS-003", "MRI lumbar spine with and without contrast", "yes", 1, 1,
     "Requires prior authorisation."),
    ("MRI-LS-004", "CT lumbar spine", "no", 0, 1, "Alternative imaging."),
    ("MRI-LS-005", "X-ray lumbar spine", "no", 0, 1, "Initial imaging."),
    ("SPINE-FUSION-001", "Investigational spinal fusion", "no", 1, 0,
     "Experimental exclusion under POL-4.3."),
]

ICD10 = [
    ("M54.5", "Low back pain, unspecified", "M54", "ICD-10-CM (public)"),
    ("M51.1", "Lumbar and other intervertebral disc disorders with radiculopathy", "M51", "ICD-10-CM (public)"),
    ("M54.50", "Low back pain, unspecified, site unspecified", "M54", "ICD-10-CM (public)"),
]

EOB = [
    ("EOB-001", CLAIM_ID, "2026-09-15", "MRI-LS-001", 850.00, 0.00, 0.00, 850.00, "N-03", "2026-10-01"),
]

DOCUMENTS = {
    "claim_id": CLAIM_ID,
    "documents": [
        {"document_id": "DOC-001", "name": "Imaging order", "required_by": "POL-4.1",
         "status": "present", "source": "medical_records:REC-017", "document_date": "2026-08-12",
         "requested_date": "", "note": "MRI-LS-001 ordered by the treating GP."},
        {"document_id": "DOC-002", "name": "Physiotherapy notes", "required_by": "POL-5.1",
         "status": "present", "source": "medical_records: physiotherapy rows (12 sessions)",
         "document_date": "2026-08-05",
         "requested_date": "", "note": "Twelve weekly sessions, weeks 1-12."},
        {"document_id": "DOC-003", "name": "Specialist referral letter", "required_by": "POL-6.4",
         "status": "missing", "source": "", "document_date": "",
         "requested_date": "2026-08-20",
         "note": "Requested from the treating specialist; not received. The appeal is conditional until it is supplied. Never fabricate it."},
        {"document_id": "DOC-004", "name": "Explanation of Benefits", "required_by": "POL-6.4",
         "status": "present", "source": "eob:EOB-001", "document_date": "2026-10-01",
         "requested_date": "", "note": "Shows the billed code MRI-LS-001 and the zero payment."},
        {"document_id": "DOC-005", "name": "Clinical notes", "required_by": "POL-5.1",
         "status": "present", "source": "medical_records: all dated rows",
         "document_date": "2026-09-20",
         "requested_date": "", "note": "Dated GP, physiotherapy and specialist-admin notes."},
    ],
}


def write_csv(path: Path, fieldnames: list[str], rows: list[tuple]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(fieldnames)
        writer.writerows(rows)


def medical_records() -> list[tuple]:
    rows: list[tuple] = []

    def add(record_date: str, record_type: str, provider: str, summary: str,
            diagnosis: str, procedure: str, weeks: int, notes: str) -> None:
        rows.append((f"REC-{len(rows) + 1:03d}", record_date, record_type, provider,
                     summary, diagnosis, procedure, weeks, notes))

    add("2026-05-12", "GP consultation", "Dr Chen (GP)",
        "Low back pain, no red flags; referred to physiotherapy.", "M54.5", "", 0,
        "Pain 7/10. Commenced analgesia and physiotherapy referral.")
    start = date(2026, 5, 20)
    for week in range(1, 13):
        visit = start + timedelta(days=7 * (week - 1))
        add(visit.isoformat(), "Physiotherapy", "Northside Physiotherapy",
            f"Physiotherapy session {week} of 12; home exercise programme.", "M54.5", "", week,
            f"Attended week {week}; pain improved from 7/10 to 4/10.")
        if week == 3:
            add("2026-06-10", "GP review", "Dr Chen (GP)",
                "NSAID trial commenced; continue physiotherapy.", "M54.5", "", week,
                "Naproxen 500 mg twice daily for four weeks; no adverse effects.")
        if week == 7:
            add("2026-07-01", "Physiotherapy review", "Northside Physiotherapy",
                "Progress review; continue programme.", "M54.5", "", week,
                "Range of motion improved; pain 5/10.")
    add("2026-08-12", "GP consultation", "Dr Chen (GP)",
        "Twelve weeks of conservative therapy completed; MRI requested; specialist referral requested.",
        "M54.5", "MRI-LS-001", 12,
        "MRI lumbar spine without contrast ordered. Specialist letter requested the same day.")
    add("2026-08-20", "Specialist administration", "Ava's specialist",
        "Referral letter requested from the specialist; not received.", "M54.5", "", 12,
        "Letter still outstanding. Do not treat as present.")
    add("2026-09-02", "Claims administration", "Northbridge Health",
        "Claim submitted for MRI-LS-001.", "M54.5", "MRI-LS-001", 12,
        "Claim CLM-2026-0915 submitted.")
    add("2026-09-15", "Imaging service", "Metro Imaging",
        "MRI lumbar spine without contrast performed.", "M54.5", "MRI-LS-001", 12,
        "Service date 15 September 2026. Billed AUD 850.")
    add("2026-09-20", "Specialist administration", "Ava's specialist",
        "Second request for the specialist letter; still outstanding.", "M54.5", "", 12,
        "Left voicemail. Letter not received by the appeal date.")
    return rows


def main() -> None:
    write_csv(SRC / "policy_clauses.csv",
              ["clause_id", "section", "title", "text", "effective_date", "version", "applies_to"],
              POLICY)
    write_csv(SRC / "denial_reasons.csv",
              ["reason_id", "reason_text", "cited_clause", "cited_code", "cited_diagnosis",
               "denial_date", "reviewer", "appeal_deadline"],
              DENIAL)
    write_csv(SRC / "medical_records.csv",
              ["record_id", "record_date", "record_type", "provider", "summary",
               "diagnosis_code", "procedure_code", "weeks_of_therapy", "notes"],
              medical_records())
    write_csv(SRC / "eob.csv",
              ["eob_id", "claim_id", "service_date", "procedure_code", "billed_amount",
               "allowed_amount", "paid_amount", "patient_responsibility", "denial_code", "denial_date"],
              EOB)
    write_csv(SRC / "procedure_codes.csv",
              ["code", "description", "contrast", "prior_auth_required", "covered", "notes"],
              CODES)
    (SRC / "claim_documents.json").write_text(
        json.dumps(DOCUMENTS, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv(
        SRC / "claim_documents.csv",
        ["document_id", "claim_id", "name", "required_by", "status", "source",
         "document_date", "requested_date", "note"],
        [(doc["document_id"], DOCUMENTS["claim_id"], doc["name"], doc["required_by"],
          doc["status"], doc.get("source", ""), doc.get("document_date", ""),
          doc.get("requested_date", ""), doc.get("note", ""))
         for doc in DOCUMENTS["documents"]],
    )
    write_csv(
        SRC / "icd10_codes.csv",
        ["code", "description", "category", "source"],
        ICD10,
    )
    (SRC / "icd10_codes.json").write_text(
        json.dumps([{"code": code, "description": description, "category": category, "source": source}
                    for code, description, category, source in ICD10], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(f"wrote {len(POLICY)} policy clauses, {len(DENIAL)} denial reasons, "
          f"{len(medical_records())} medical records, {len(EOB)} EOB rows, "
          f"{len(CODES)} procedure codes, {len(DOCUMENTS['documents'])} documents")


if __name__ == "__main__":
    main()
