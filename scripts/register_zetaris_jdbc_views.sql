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
FROM OVERTURN_DB.denial_reasons d
LEFT JOIN OVERTURN_DB.policy_clauses p   ON p.clause_id = d.cited_clause
LEFT JOIN OVERTURN_DB.procedure_codes c  ON c.code = d.cited_code
LEFT JOIN OVERTURN_DB.icd10_codes i      ON i.code = d.cited_diagnosis;

CREATE SCHEMASTORE VIEW claim_facts WITH CONTAINER overturn_db AS
SELECT
  (SELECT MAX(weeks_of_therapy) FROM OVERTURN_DB.medical_records) AS max_weeks_of_therapy,
  (SELECT COUNT(*) FROM OVERTURN_DB.medical_records WHERE record_type = 'Physiotherapy') AS physiotherapy_sessions,
  (SELECT procedure_code FROM OVERTURN_DB.medical_records
     WHERE procedure_code IS NOT NULL AND procedure_code <> ''
     ORDER BY record_date DESC LIMIT 1) AS ordered_procedure_code,
  (SELECT diagnosis_code FROM OVERTURN_DB.medical_records
     WHERE diagnosis_code IS NOT NULL AND diagnosis_code <> ''
     ORDER BY record_date DESC LIMIT 1) AS recorded_diagnosis_code,
  (SELECT COUNT(*) FROM OVERTURN_DB.claim_documents WHERE status = 'missing') AS missing_documents;

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
  (SELECT MIN(document_id) FROM OVERTURN_DB.claim_documents WHERE status = 'missing') AS first_missing_document
FROM OVERTURN_DB.denial_reasons d
LEFT JOIN OVERTURN_DB.policy_clauses p   ON p.clause_id = d.cited_clause
LEFT JOIN OVERTURN_DB.procedure_codes c  ON c.code = d.cited_code
LEFT JOIN OVERTURN_DB.icd10_codes i      ON i.code = d.cited_diagnosis
CROSS JOIN OVERTURN_DB.claim_facts f;

CREATE SCHEMASTORE VIEW dq_claim_integrity WITH CONTAINER overturn_db AS
SELECT 'DQ-01' AS rule_id,
       'every denial reason cites a policy clause that exists' AS rule,
       (SELECT COUNT(*) FROM OVERTURN_DB.denial_reasons d
          LEFT JOIN OVERTURN_DB.policy_clauses p ON p.clause_id = d.cited_clause
         WHERE p.clause_id IS NULL) AS failures,
       CASE WHEN (SELECT COUNT(*) FROM OVERTURN_DB.denial_reasons d
                    LEFT JOIN OVERTURN_DB.policy_clauses p ON p.clause_id = d.cited_clause
                   WHERE p.clause_id IS NULL) = 0 THEN 'pass' ELSE 'fail' END AS status
UNION ALL
SELECT 'DQ-02',
       'every cited procedure code exists in the code table',
       (SELECT COUNT(*) FROM OVERTURN_DB.denial_reasons d
          LEFT JOIN OVERTURN_DB.procedure_codes c ON c.code = d.cited_code
         WHERE c.code IS NULL),
       CASE WHEN (SELECT COUNT(*) FROM OVERTURN_DB.denial_reasons d
                    LEFT JOIN OVERTURN_DB.procedure_codes c ON c.code = d.cited_code
                   WHERE c.code IS NULL) = 0 THEN 'pass' ELSE 'fail' END
UNION ALL
SELECT 'DQ-03',
       'every clinical record has a date and a provider',
       (SELECT COUNT(*) FROM OVERTURN_DB.medical_records
         WHERE record_date IS NULL OR provider IS NULL OR provider = ''),
       CASE WHEN (SELECT COUNT(*) FROM OVERTURN_DB.medical_records
                    WHERE record_date IS NULL OR provider IS NULL OR provider = '') = 0
            THEN 'pass' ELSE 'fail' END
UNION ALL
SELECT 'DQ-04',
       'a missing required document is flagged and has no fabricated date',
       (SELECT COUNT(*) FROM OVERTURN_DB.claim_documents WHERE status = 'missing' AND document_date IS NOT NULL),
       CASE WHEN (SELECT COUNT(*) FROM OVERTURN_DB.claim_documents WHERE status = 'missing' AND document_date IS NOT NULL) = 0
            THEN 'pass' ELSE 'fail' END
UNION ALL
SELECT 'DQ-05',
       'the missing-document count agrees across the fact view and the documents table',
       (SELECT ABS((SELECT missing_documents FROM OVERTURN_DB.claim_facts)
                 - (SELECT COUNT(*) FROM OVERTURN_DB.claim_documents WHERE status = 'missing'))),
       CASE WHEN (SELECT missing_documents FROM OVERTURN_DB.claim_facts)
               = (SELECT COUNT(*) FROM OVERTURN_DB.claim_documents WHERE status = 'missing')
            THEN 'pass' ELSE 'fail' END;
