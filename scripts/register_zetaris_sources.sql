-- OVERTURN — Zetaris source registration
-- =====================================================================
-- Zetaris is the only data path. The Reconciler's single data tool is
-- run_sql, which executes against the tables and views registered here.
--
-- Before running:
--   1. Upload data/sources/*.csv to a bucket Zetaris can reach.
--      A laptop path is not visible to Zetaris. AWS S3 or a local MinIO
--      bucket both work. The statements below use s3a://overturn/...
--      Change the PATH, s3Endpoint and bucket options to match your install.
--   2. Set ZETARIS_USER_AGENT to a real "app_name contact@email" value.
--      The live ICD-10 REST tables reject a placeholder user agent.
--   3. Confirm the FILESTORE/REST option names against the Participant Setup
--      Guide for the deployed Zetaris version. Table names, columns and the
--      view semantics are final.
--
-- DIALECT: Zetaris Lightning SQL. One statement per call. Do not run this
-- file with a semicolon-splitting script that also splits the COMPILE
-- statement; there is no COMPILE USL here, only schemastore views.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Logical database and container
-- ---------------------------------------------------------------------

CREATE LIGHTNING DATABASE OVERTURN_DB
DESCRIBE BY "OVERTURN denial appeal evidence, policy denial clinical record EOB codes documents";

CREATE SCHEMASTORE CONTAINER overturn_db;

-- ---------------------------------------------------------------------
-- 2. File-backed sources (CSV in an S3/MinIO bucket)
-- Replace the PATH and S3 options with the bucket that holds data/sources.
-- MinIO example:
--   s3Endpoint "http://localhost:9000"
--   useS3PathStyleAccess "true"
-- AWS S3 example:
--   s3Endpoint "s3.ap-southeast-2.amazonaws.com"
--   isS3BucketPublic "false"
-- Supply credentials through the Zetaris connector configuration, not in
-- this file and not in the repository.
-- ---------------------------------------------------------------------

CREATE LIGHTNING FILESTORE TABLE policy_clauses FROM OVERTURN_DB FORMAT CSV OPTIONS (
  PATH "s3a://overturn/policy_clauses.csv",
  inferSchema "true",
  header "true",
  useS3PathStyleAccess "true",
  s3Endpoint "http://localhost:9000"
);

CREATE LIGHTNING FILESTORE TABLE denial_reasons FROM OVERTURN_DB FORMAT CSV OPTIONS (
  PATH "s3a://overturn/denial_reasons.csv",
  inferSchema "true",
  header "true",
  useS3PathStyleAccess "true",
  s3Endpoint "http://localhost:9000"
);

CREATE LIGHTNING FILESTORE TABLE medical_records FROM OVERTURN_DB FORMAT CSV OPTIONS (
  PATH "s3a://overturn/medical_records.csv",
  inferSchema "true",
  header "true",
  useS3PathStyleAccess "true",
  s3Endpoint "http://localhost:9000"
);

CREATE LIGHTNING FILESTORE TABLE eob FROM OVERTURN_DB FORMAT CSV OPTIONS (
  PATH "s3a://overturn/eob.csv",
  inferSchema "true",
  header "true",
  useS3PathStyleAccess "true",
  s3Endpoint "http://localhost:9000"
);

CREATE LIGHTNING FILESTORE TABLE procedure_codes FROM OVERTURN_DB FORMAT CSV OPTIONS (
  PATH "s3a://overturn/procedure_codes.csv",
  inferSchema "true",
  header "true",
  useS3PathStyleAccess "true",
  s3Endpoint "http://localhost:9000"
);

CREATE LIGHTNING FILESTORE TABLE claim_documents FROM OVERTURN_DB FORMAT CSV OPTIONS (
  PATH "s3a://overturn/claim_documents.csv",
  inferSchema "true",
  header "true",
  useS3PathStyleAccess "true",
  s3Endpoint "http://localhost:9000"
);

-- Cached public ICD-10-CM descriptions, so SAMPLE_MODE and live mode can
-- answer the same diagnosis-code question deterministically.
CREATE LIGHTNING FILESTORE TABLE icd10_codes FROM OVERTURN_DB FORMAT CSV OPTIONS (
  PATH "s3a://overturn/icd10_codes.csv",
  inferSchema "true",
  header "true",
  useS3PathStyleAccess "true",
  s3Endpoint "http://localhost:9000"
);

-- ---------------------------------------------------------------------
-- 3. Live public REST source — ICD-10-CM search (no API key)
-- The public endpoint returns a JSON array: [count, codes, extra, display].
-- The statement registers one endpoint per code so the table is a stable
-- row set. The deterministic pipeline queries the cached icd10_codes table;
-- these live tables are the connectivity proof and can be flattened into a
-- live view once DESCRIBE confirms the inferred column names.
--
-- Set ZETARIS_USER_AGENT to a real "app_name contact@email" value before
-- running these statements.
-- ---------------------------------------------------------------------

CREATE LIGHTNING REST TABLE icd10_m545 FROM OVERTURN_DB REQUEST (
  endpoint "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search?terms=M54.5",
  method "get",
  response_type "json",
  http_encoding "URLENCODED"
) HEADER (
  user-agent "OVERTURN hackathon you@example.invalid"
) BODY ();

CREATE LIGHTNING REST TABLE icd10_m511 FROM OVERTURN_DB REQUEST (
  endpoint "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search?terms=M51.1",
  method "get",
  response_type "json",
  http_encoding "URLENCODED"
) HEADER (
  user-agent "OVERTURN hackathon you@example.invalid"
) BODY ();

CACHE TABLE OVERTURN.icd10_m545;
CACHE TABLE OVERTURN.icd10_m511;

-- ---------------------------------------------------------------------
-- 4. Semantic views
-- ---------------------------------------------------------------------

CREATE SCHEMASTORE VIEW appeal_evidence WITH CONTAINER overturn_db AS
SELECT
  d.reason_id,
  d.reason_text,
  d.cited_clause,
  d.cited_code,
  d.cited_diagnosis,
  d.denial_date,
  d.appeal_deadline,
  p.clause_id,
  p.title              AS clause_title,
  p.text               AS clause_text,
  p.applies_to,
  c.description        AS code_description,
  c.prior_auth_required,
  c.covered,
  i.description        AS diagnosis_description
FROM denial_reasons d
LEFT JOIN policy_clauses p   ON p.clause_id = d.cited_clause
LEFT JOIN procedure_codes c  ON c.code = d.cited_code
LEFT JOIN icd10_codes i      ON i.code = d.cited_diagnosis;

CREATE SCHEMASTORE VIEW claim_facts WITH CONTAINER overturn_db AS
SELECT
  (SELECT MAX(weeks_of_therapy) FROM medical_records) AS max_weeks_of_therapy,
  (SELECT COUNT(*) FROM medical_records WHERE record_type = 'Physiotherapy') AS physiotherapy_sessions,
  (SELECT procedure_code FROM medical_records
     WHERE procedure_code IS NOT NULL AND procedure_code <> ''
     ORDER BY record_date DESC LIMIT 1) AS ordered_procedure_code,
  (SELECT diagnosis_code FROM medical_records
     WHERE diagnosis_code IS NOT NULL AND diagnosis_code <> ''
     ORDER BY record_date DESC LIMIT 1) AS recorded_diagnosis_code,
  (SELECT COUNT(*) FROM claim_documents WHERE status = 'missing') AS missing_documents;

-- ---------------------------------------------------------------------
-- 4b. The Unified Semantic Layer (USL)
--
-- The USL is the `overturn` schemastore container plus these three views.
-- `usl_claim_review` is the business entity a judge can query: one row per
-- denial reason, fully attributed to the policy clause, procedure code,
-- diagnosis and claim facts. `appeal_evidence` is the evidence-level join;
-- `claim_facts` is the claim-level measure set.
-- ---------------------------------------------------------------------

CREATE SCHEMASTORE VIEW usl_claim_review WITH CONTAINER overturn_db AS
SELECT
  d.reason_id,
  d.reason_text,
  d.denial_date,
  d.appeal_deadline,
  d.cited_clause,
  p.title              AS clause_title,
  p.text               AS clause_text,
  p.applies_to,
  d.cited_code,
  c.description        AS code_description,
  c.contrast,
  c.prior_auth_required,
  c.covered,
  d.cited_diagnosis,
  i.description        AS diagnosis_description,
  f.max_weeks_of_therapy,
  f.physiotherapy_sessions,
  f.ordered_procedure_code,
  f.recorded_diagnosis_code,
  f.missing_documents,
  (SELECT MIN(document_id) FROM claim_documents WHERE status = 'missing') AS first_missing_document
FROM denial_reasons d
LEFT JOIN policy_clauses p   ON p.clause_id = d.cited_clause
LEFT JOIN procedure_codes c  ON c.code = d.cited_code
LEFT JOIN icd10_codes i      ON i.code = d.cited_diagnosis
CROSS JOIN claim_facts f;

-- ---------------------------------------------------------------------
-- 4c. Data quality rules
--
-- One view, five rules, one row per rule. `failures` is the number of rows
-- that violate the rule; `status` is pass/fail. The expected result is 0
-- failures on every rule for the Ava case.
-- ---------------------------------------------------------------------

CREATE SCHEMASTORE VIEW dq_claim_integrity WITH CONTAINER overturn_db AS
SELECT 'DQ-01' AS rule_id,
       'every denial reason cites a policy clause that exists' AS rule,
       (SELECT COUNT(*) FROM denial_reasons d
          LEFT JOIN policy_clauses p ON p.clause_id = d.cited_clause
         WHERE p.clause_id IS NULL) AS failures,
       CASE WHEN (SELECT COUNT(*) FROM denial_reasons d
                    LEFT JOIN policy_clauses p ON p.clause_id = d.cited_clause
                   WHERE p.clause_id IS NULL) = 0 THEN 'pass' ELSE 'fail' END AS status
UNION ALL
SELECT 'DQ-02',
       'every cited procedure code exists in the code table',
       (SELECT COUNT(*) FROM denial_reasons d
          LEFT JOIN procedure_codes c ON c.code = d.cited_code
         WHERE c.code IS NULL),
       CASE WHEN (SELECT COUNT(*) FROM denial_reasons d
                    LEFT JOIN procedure_codes c ON c.code = d.cited_code
                   WHERE c.code IS NULL) = 0 THEN 'pass' ELSE 'fail' END
UNION ALL
SELECT 'DQ-03',
       'every clinical record has a date and a provider',
       (SELECT COUNT(*) FROM medical_records
         WHERE record_date IS NULL OR provider IS NULL OR provider = ''),
       CASE WHEN (SELECT COUNT(*) FROM medical_records
                    WHERE record_date IS NULL OR provider IS NULL OR provider = '') = 0
            THEN 'pass' ELSE 'fail' END
UNION ALL
SELECT 'DQ-04',
       'a missing required document is flagged and has no fabricated date',
       (SELECT COUNT(*) FROM claim_documents WHERE status = 'missing' AND document_date IS NOT NULL),
       CASE WHEN (SELECT COUNT(*) FROM claim_documents WHERE status = 'missing' AND document_date IS NOT NULL) = 0
            THEN 'pass' ELSE 'fail' END
UNION ALL
SELECT 'DQ-05',
       'the missing-document count agrees across the fact view and the documents table',
       (SELECT ABS((SELECT missing_documents FROM claim_facts)
                 - (SELECT COUNT(*) FROM claim_documents WHERE status = 'missing'))),
       CASE WHEN (SELECT missing_documents FROM claim_facts)
               = (SELECT COUNT(*) FROM claim_documents WHERE status = 'missing')
            THEN 'pass' ELSE 'fail' END;

-- ---------------------------------------------------------------------
-- 5. USL verification queries
-- These are the "show the USL is active" queries a judge can run.
-- ---------------------------------------------------------------------

-- USL-1: one row per denial reason, fully attributed (expect 4).
SELECT reason_id, cited_clause, clause_title, code_description,
       diagnosis_description, missing_documents
FROM usl_claim_review
ORDER BY reason_id;

-- USL-2: the code mismatch. DEN-02 cites MRI-LS-002; the order and record
-- use MRI-LS-001.
SELECT reason_id, cited_code, code_description,
       ordered_procedure_code, recorded_diagnosis_code, cited_diagnosis
FROM usl_claim_review
WHERE reason_id = 'DEN-02';

-- USL-3: the medical-necessity facts (expect 12 sessions and 12 weeks).
SELECT reason_id, physiotherapy_sessions, max_weeks_of_therapy
FROM usl_claim_review
WHERE reason_id = 'DEN-03';

-- USL-4: all five data quality rules should pass.
SELECT rule_id, rule, failures, status
FROM dq_claim_integrity
ORDER BY rule_id;

-- ---------------------------------------------------------------------
-- 6. Source-by-source verification
-- Two queries per source, as the Zetaris evaluation asks for.
-- ---------------------------------------------------------------------

-- policy_clauses (12 rows)
SELECT COUNT(*) AS policy_clauses FROM policy_clauses;
SELECT clause_id, section, title, applies_to FROM policy_clauses
WHERE clause_id IN ('POL-4.1', 'POL-4.3', 'POL-5.1', 'POL-6.4')
ORDER BY clause_id;

-- denial_reasons (4 rows)
SELECT COUNT(*) AS denial_reasons FROM denial_reasons;
SELECT reason_id, denial_date, appeal_deadline, reviewer FROM denial_reasons
ORDER BY reason_id;

-- medical_records (20 rows)
SELECT COUNT(*) AS medical_records FROM medical_records;
SELECT record_type, COUNT(*) AS n, MAX(weeks_of_therapy) AS max_weeks
FROM medical_records GROUP BY record_type ORDER BY record_type;

-- eob (1 row)
SELECT COUNT(*) AS eob FROM eob;
SELECT eob_id, claim_id, service_date, procedure_code, billed_amount, paid_amount
FROM eob;

-- procedure_codes (6 rows)
SELECT COUNT(*) AS procedure_codes FROM procedure_codes;
SELECT code, description, contrast, prior_auth_required, covered
FROM procedure_codes WHERE code IN ('MRI-LS-001', 'MRI-LS-002') ORDER BY code;

-- claim_documents (5 rows)
SELECT COUNT(*) AS claim_documents FROM claim_documents;
SELECT status, COUNT(*) AS n FROM claim_documents GROUP BY status ORDER BY status;

-- icd10_codes (3 rows)
SELECT COUNT(*) AS icd10_codes FROM icd10_codes;
SELECT code, description FROM icd10_codes ORDER BY code;

-- ---------------------------------------------------------------------
-- 7. Smoke queries
-- ---------------------------------------------------------------------

-- Row counts: expect 12, 4, 20, 1, 6, 5, 3
SELECT 'policy_clauses' AS t, COUNT(*) AS n FROM policy_clauses
UNION ALL SELECT 'denial_reasons', COUNT(*) FROM denial_reasons
UNION ALL SELECT 'medical_records', COUNT(*) FROM medical_records
UNION ALL SELECT 'eob', COUNT(*) FROM eob
UNION ALL SELECT 'procedure_codes', COUNT(*) FROM procedure_codes
UNION ALL SELECT 'claim_documents', COUNT(*) FROM claim_documents
UNION ALL SELECT 'icd10_codes', COUNT(*) FROM icd10_codes;

-- C1: the cited clause excludes diagnostic MRI by its own text.
SELECT clause_id, applies_to, text
FROM policy_clauses
WHERE clause_id IN ('POL-4.3', 'POL-4.1')
ORDER BY clause_id;

-- C2: the denial's code and diagnosis vs the EOB/record.
SELECT d.reason_id, d.cited_code, d.cited_diagnosis,
       e.procedure_code AS eob_code
FROM denial_reasons d
CROSS JOIN eob e
WHERE d.reason_id = 'DEN-02';

-- C3: 12 physiotherapy sessions and 12 weeks.
SELECT COUNT(*) AS physiotherapy_sessions, MAX(weeks_of_therapy) AS max_weeks
FROM medical_records
WHERE record_type = 'Physiotherapy';

-- C4: the missing required document.
SELECT document_id, name, required_by, status, requested_date, note
FROM claim_documents
WHERE status = 'missing';

-- The joined evidence view.
SELECT reason_id, cited_clause, applies_to, code_description, diagnosis_description
FROM appeal_evidence
ORDER BY reason_id;

-- Live REST proof: these rows come from the public ICD-10 endpoint.
-- Run DESCRIBE OVERTURN.icd10_m545; first and adapt the column names if the
-- JSON inference differs.
SELECT * FROM icd10_m545;
SELECT * FROM icd10_m511;
