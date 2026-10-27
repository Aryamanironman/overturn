# Zetaris data layer — the Unified Semantic Layer

The Zetaris build criteria ask for five things: **3+ sources**, **2–3 queries
per source**, **one Unified Semantic Layer and its DDL**, **queries showing the
USL is active**, and **one data quality rule**. This document maps each one to
the exact artefact in the repository. All of it is in
`scripts/register_zetaris_sources.sql`.

## 1. Sources — seven

| Table | Rows | What it holds |
|---|---:|---|
| `policy_clauses` | 12 | The clauses the denial cites, and the clauses that actually apply |
| `denial_reasons` | 4 | DEN-01…DEN-04 with cited clause, code, diagnosis, deadline |
| `medical_records` | 20 | Dated GP, physiotherapy and admin notes; 12 physio sessions |
| `eob` | 1 | EOB-001: MRI-LS-001, billed AUD 850, paid 0 |
| `procedure_codes` | 6 | MRI-LS-001…005 and SPINE-FUSION-001, with contrast/prior-auth flags |
| `claim_documents` | 5 | DOC-001…DOC-005; DOC-003 is `missing` |
| `icd10_codes` | 3 | Public ICD-10-CM descriptions for M54.5, M51.1, M54.50 |

Two live REST tables (`icd10_m545`, `icd10_m511`) against the public
Clinical Tables API prove live source connectivity.

## 2. The USL and its DDL

The USL is the `overturn` schemastore container plus three views. The DDL is
section 4/4b of `scripts/register_zetaris_sources.sql`.

- **`usl_claim_review`** — the business entity. One row per denial reason,
  fully attributed: the cited policy clause and its text, the cited procedure
  code and its coverage/prior-auth flags, the cited diagnosis, and the
  claim-level facts (physio sessions, weeks of therapy, ordered code, recorded
  diagnosis, missing-document count, first missing document).
- **`appeal_evidence`** — the evidence-level join across denial, policy,
  procedure code and diagnosis.
- **`claim_facts`** — the claim-level measures: `max_weeks_of_therapy`,
  `physiotherapy_sessions`, `ordered_procedure_code`,
  `recorded_diagnosis_code`, `missing_documents`.

The semantic model:

| Layer | Definition |
|---|---|
| Entities | claim, denial reason, policy clause, procedure code, diagnosis, clinical record, document |
| Relationships | reason → cited clause / code / diagnosis; records, documents and EOB → claim |
| Measures | rebutted reasons, missing documents, physiotherapy sessions/weeks, code mismatch, prior-auth requirement |
| Dimensions | reason, clause, procedure code, diagnosis, record type, document status |

## 3. USL-active queries

Section 5 of the SQL file. A judge can run these as-is:

| Query | Expected result |
|---|---|
| `USL-1` | 4 rows, one per denial reason, each with clause title, code description, diagnosis description and missing-document count |
| `USL-2` | `DEN-02` cites `MRI-LS-002`, while the order and record use `MRI-LS-001` |
| `USL-3` | `DEN-03` has 12 physiotherapy sessions and 12 weeks of therapy |
| `USL-4` | 5 data-quality rows, all `pass` with 0 failures |

## 4. Data quality rule

`dq_claim_integrity` (section 4c) is one view with five rules, one row per
rule, `failures` and `pass|fail`:

| Rule | What it catches |
|---|---|
| `DQ-01` | A denial reason citing a policy clause that does not exist |
| `DQ-02` | A cited procedure code missing from the code table |
| `DQ-03` | A clinical record with no date or provider |
| `DQ-04` | A missing document that has been given a fabricated date |
| `DQ-05` | The missing-document count disagreeing between `claim_facts` and `claim_documents` |

The Ava case passes all five. The rules are part of the data layer, not a
one-off query: a judge can re-run `SELECT * FROM dq_claim_integrity` after
changing a source and see which rule breaks.

## 5. Per-source verification

Section 6 of the SQL file has two queries for each of the seven sources:
a row count and a column-level check (e.g. the two MRI codes' contrast and
prior-auth flags, the 12/12 physiotherapy facts, the document status split).

## How to run it

1. Upload `data/sources/*.csv` to an S3-compatible bucket Zetaris can reach
   (AWS S3 or local MinIO) and set `PATH` / `s3Endpoint` in the SQL file.
2. Run the file one complete statement at a time in the Zetaris SQL Editor,
   in order. The file says this explicitly: do not split a statement.
3. Run the USL and DQ queries in sections 5–6.

`tests/test_usl_views.py` executes the shipped `usl_claim_review` and
`dq_claim_integrity` bodies against the SQLite mirror. It fails if the views
and the case facts drift: 4 reason rows, the DEN-02 code mismatch, 12/12
physiotherapy, DOC-003 missing, and all five DQ rules passing.
