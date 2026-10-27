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

CREATE LIGHTNING DATABASE OVERTURN
DESCRIBE BY "OVERTURN — denial appeal evidence: policy, denial, clinical record, EOB, codes, documents";

CREATE SCHEMASTORE CONTAINER overturn;

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

CREATE LIGHTNING FILESTORE TABLE policy_clauses FROM OVERTURN FORMAT CSV OPTIONS (
  PATH "s3a://overturn/policy_clauses.csv",
  inferSchema "true",
  header "true",
  useS3PathStyleAccess "true",
  s3Endpoint "http://localhost:9000"
);

CREATE LIGHTNING FILESTORE TABLE denial_reasons FROM OVERTURN FORMAT CSV OPTIONS (
  PATH "s3a://overturn/denial_reasons.csv",
  inferSchema "true",
  header "true",
  useS3PathStyleAccess "true",
  s3Endpoint "http://localhost:9000"
);

CREATE LIGHTNING FILESTORE TABLE medical_records FROM OVERTURN FORMAT CSV OPTIONS (
  PATH "s3a://overturn/medical_records.csv",
  inferSchema "true",
  header "true",
  useS3PathStyleAccess "true",
  s3Endpoint "http://localhost:9000"
);

CREATE LIGHTNING FILESTORE TABLE eob FROM OVERTURN FORMAT CSV OPTIONS (
  PATH "s3a://overturn/eob.csv",
  inferSchema "true",
  header "true",
  useS3PathStyleAccess "true",
  s3Endpoint "http://localhost:9000"
);

CREATE LIGHTNING FILESTORE TABLE procedure_codes FROM OVERTURN FORMAT CSV OPTIONS (
  PATH "s3a://overturn/procedure_codes.csv",
  inferSchema "true",
  header "true",
  useS3PathStyleAccess "true",
  s3Endpoint "http://localhost:9000"
);

CREATE LIGHTNING FILESTORE TABLE claim_documents FROM OVERTURN FORMAT CSV OPTIONS (
  PATH "s3a://overturn/claim_documents.csv",
  inferSchema "true",
  header "true",
  useS3PathStyleAccess "true",
  s3Endpoint "http://localhost:9000"
);

-- Cached public ICD-10-CM descriptions, so SAMPLE_MODE and live mode can
-- answer the same diagnosis-code question deterministically.
CREATE LIGHTNING FILESTORE TABLE icd10_codes FROM OVERTURN FORMAT CSV OPTIONS (
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

CREATE LIGHTNING REST TABLE icd10_m545 FROM OVERTURN REQUEST (
  endpoint "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search?terms=M54.5",
  method "get",
  response_type "json",
  http_encoding "URLENCODED"
) HEADER (
  user-agent "OVERTURN hackathon you@example.invalid"
) BODY ();

CREATE LIGHTNING REST TABLE icd10_m511 FROM OVERTURN REQUEST (
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

CREATE SCHEMASTORE VIEW appeal_evidence WITH CONTAINER overturn AS
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

CREATE SCHEMASTORE VIEW claim_facts WITH CONTAINER overturn AS
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
-- 5. Smoke queries
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
