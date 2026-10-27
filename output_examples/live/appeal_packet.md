# OVERTURN — Internal Appeal Packet
**Claimant:** Ava  
**Insurer:** Northbridge Health  
**Claim:** CLM-2026-0915  
**Denial date:** 2026-10-01  
**Appeal deadline:** 2026-11-30  
**Procedure:** MRI-LS-001 — MRI lumbar spine without contrast  
**Diagnosis:** M54.5 — Low back pain, unspecified

## Appeal strength
**84 / 100 — solid — conditional.**  
Raw 90, capped at 84 because a required document is missing.  
This is an evidence-strength score, not a prediction of the insurer's decision. A human must review and sign the packet.

### Send this first
- **Specialist referral letter** (DOC-003) — required by POL-6.4. Requested from the treating specialist; not received. The appeal is conditional until it is supplied. Never fabricate it.

## Why the denial is wrong
| Reason | Status | Rebuttal | Sources |
|---|---|---|---|
| DEN-01 — The service is experimental or investigational. | rebutted | The denial cites POL-4.3, the experimental exclusion. That clause applies to SPINE-FUSION-001 and states it does not apply to diagnostic MRI of the lumbar spine. POL-4.1 covers MRI-LS-001 after at least six weeks of conservative therapy. | policy_clauses:POL-4.3, policy_clauses:POL-4.1, medical_records:REC-016, eob:EOB-001 |
| DEN-02 — Procedure code MRI-LS-002 (MRI with contrast) is not covered without prior authorisation. | rebutted | The denial cites MRI-LS-002 and diagnosis M51.1. The order, the EOB and the record use MRI-LS-001 and diagnosis M54.5. MRI-LS-001 is described as 'MRI lumbar spine without contrast' and does not require prior authorisation; MRI-LS-002 is the contrast study that does. | procedure_codes:MRI-LS-002, procedure_codes:MRI-LS-001, eob:EOB-001, medical_records:REC-016, icd10_codes:M51.1, icd10_codes:M54.5 |
| DEN-03 — No conservative treatment is documented. | rebutted | The record documents 12 physiotherapy sessions over 12 weeks and an NSAID trial. POL-5.1 requires at least six weeks of conservative therapy. | policy_clauses:POL-5.1, medical_records:REC-016, medical_records:REC-005, medical_records:REC-002, medical_records:REC-003, medical_records:REC-004, medical_records:REC-006, medical_records:REC-007, medical_records:REC-008, medical_records:REC-009, medical_records:REC-011, medical_records:REC-012, medical_records:REC-013, medical_records:REC-014, medical_records:REC-015 |
| DEN-04 — A specialist referral letter was not provided. | missing | This required document is genuinely missing from the file. It is listed in the checklist and will be supplied. It has not been fabricated. | policy_clauses:POL-6.4, claim_documents:DOC-003 |

## Cover letter
I am requesting an internal appeal of Northbridge Health's denial dated 2026-10-01 for claim CLM-2026-0915. The denial gives 4 reasons; 3 are contradicted by the policy, the clinical record or the coding. The remaining reason concerns a missing required document: Specialist referral letter (DOC-003). It is listed in the checklist and will be supplied; it has not been fabricated. The evidence for each reason is indexed below.

## Evidence index
| Line | Source | Date | Summary | Status | Hash |
|---|---|---|---|---|---|
| L0001 | policy_clauses:POL-4.1 | 2026-01-01 | POL-4.1 Covered imaging: MRI lumbar spine without contrast (MRI-LS-001) is covered when the member has completed at least six weeks of conservative therapy. | reference | `38837de8ccee…` |
| L0002 | policy_clauses:POL-4.2 | 2026-01-01 | POL-4.2 Prior authorisation: MRI lumbar spine without contrast (MRI-LS-001) does not require prior authorisation. Contrast studies (MRI-LS-002, MRI-LS-003) require prior authorisation. | reference | `655e8b053483…` |
| L0003 | policy_clauses:POL-4.3 | 2026-01-01 | POL-4.3 Experimental or investigational: The experimental exclusion applies to spinal fusion (SPINE-FUSION-001) and disc replacement. It does not apply to diagnostic MRI of the lumbar spine. | reference | `40b872ed4ff8…` |
| L0004 | policy_clauses:POL-5.1 | 2026-01-01 | POL-5.1 Medical necessity: Lumbar imaging is medically necessary when the clinical record documents failed conservative treatment for at least six weeks, including physiotherapy or analgesic medication. | reference | `616314173e08…` |
| L0005 | policy_clauses:POL-5.2 | 2026-01-01 | POL-5.2 Conservative therapy: Conservative therapy includes physiotherapy, a structured home exercise programme and analgesic medication. | reference | `a2144b1cb27d…` |
| L0006 | policy_clauses:POL-6.4 | 2026-01-01 | POL-6.4 Claim documentation: An imaging claim must include a specialist referral letter dated after the imaging order. Without it the claim is incomplete. | reference | `84a6861f44dd…` |
| L0007 | policy_clauses:POL-7.2 | 2026-01-01 | POL-7.2 Claim edits: Procedure code MRI-LS-002 (MRI with contrast) requires prior authorisation. MRI-LS-001 (without contrast) does not. | reference | `8d8531ea3c4b…` |
| L0008 | policy_clauses:POL-8.1 | 2026-01-01 | POL-8.1 Internal appeal: A member may request an internal appeal within 60 days of the denial date. | reference | `b4cbf718562c…` |
| L0009 | policy_clauses:POL-9.3 | 2026-01-01 | POL-9.3 Policy version: Version 2026.1 is effective 1 January 2026 and supersedes version 2025.3. | reference | `05d1e7c4dd9b…` |
| L0010 | policy_clauses:POL-10.1 | 2026-01-01 | POL-10.1 Definitions: A specialist referral letter is a letter from the treating specialist that recommends the imaging and is dated after the imaging order. | reference | `e52eeeb787e7…` |
| L0011 | policy_clauses:POL-12.4 | 2026-01-01 | POL-12.4 Clinical records: Clinical records must be dated and attributable to a treating provider. | reference | `57ce7fd773ef…` |
| L0012 | policy_clauses:POL-13.1 | 2026-01-01 | POL-13.1 Response time: The insurer must respond to an internal appeal within 30 days of receiving it. | reference | `b14a6c759dff…` |
| L0013 | medical_records:REC-001 | 2026-05-12 | GP consultation 2026-05-12: Low back pain, no red flags; referred to physiotherapy. | documented | `dfc3cd70969c…` |
| L0014 | medical_records:REC-002 | 2026-05-20 | Physiotherapy 2026-05-20: Physiotherapy session 1 of 12; home exercise programme. | documented | `a94071d5cbd0…` |
| L0015 | medical_records:REC-003 | 2026-05-27 | Physiotherapy 2026-05-27: Physiotherapy session 2 of 12; home exercise programme. | documented | `9bf8a9422389…` |
| L0016 | medical_records:REC-004 | 2026-06-03 | Physiotherapy 2026-06-03: Physiotherapy session 3 of 12; home exercise programme. | documented | `a164873fcf0d…` |
| L0017 | medical_records:REC-005 | 2026-06-10 | GP review 2026-06-10: NSAID trial commenced; continue physiotherapy. | documented | `d4a97f90ce90…` |
| L0018 | medical_records:REC-006 | 2026-06-10 | Physiotherapy 2026-06-10: Physiotherapy session 4 of 12; home exercise programme. | documented | `cad328d55cbb…` |
| L0019 | medical_records:REC-007 | 2026-06-17 | Physiotherapy 2026-06-17: Physiotherapy session 5 of 12; home exercise programme. | documented | `0cd087d62454…` |
| L0020 | medical_records:REC-008 | 2026-06-24 | Physiotherapy 2026-06-24: Physiotherapy session 6 of 12; home exercise programme. | documented | `e007642c75f5…` |
| L0021 | medical_records:REC-009 | 2026-07-01 | Physiotherapy 2026-07-01: Physiotherapy session 7 of 12; home exercise programme. | documented | `7397a1be83ff…` |
| L0022 | medical_records:REC-010 | 2026-07-01 | Physiotherapy review 2026-07-01: Progress review; continue programme. | documented | `b2fecb63ab77…` |
| L0023 | medical_records:REC-011 | 2026-07-08 | Physiotherapy 2026-07-08: Physiotherapy session 8 of 12; home exercise programme. | documented | `ff6bd834b3d9…` |
| L0024 | medical_records:REC-012 | 2026-07-15 | Physiotherapy 2026-07-15: Physiotherapy session 9 of 12; home exercise programme. | documented | `fe59336cb63c…` |
| L0025 | medical_records:REC-013 | 2026-07-22 | Physiotherapy 2026-07-22: Physiotherapy session 10 of 12; home exercise programme. | documented | `518738088100…` |
| L0026 | medical_records:REC-014 | 2026-07-29 | Physiotherapy 2026-07-29: Physiotherapy session 11 of 12; home exercise programme. | documented | `3048d4bb2e14…` |
| L0027 | medical_records:REC-015 | 2026-08-05 | Physiotherapy 2026-08-05: Physiotherapy session 12 of 12; home exercise programme. | documented | `0c2a150ee659…` |
| L0028 | medical_records:REC-016 | 2026-08-12 | GP consultation 2026-08-12: Twelve weeks of conservative therapy completed; MRI requested; specialist referral requested. | documented | `a8e1a3737abc…` |
| L0029 | medical_records:REC-017 | 2026-08-20 | Specialist administration 2026-08-20: Referral letter requested from the specialist; not received. | documented | `93205044a138…` |
| L0030 | medical_records:REC-018 | 2026-09-02 | Claims administration 2026-09-02: Claim submitted for MRI-LS-001. | documented | `ad57f5897d29…` |
| L0031 | medical_records:REC-019 | 2026-09-15 | Imaging service 2026-09-15: MRI lumbar spine without contrast performed. | documented | `1061f36049e7…` |
| L0032 | medical_records:REC-020 | 2026-09-20 | Specialist administration 2026-09-20: Second request for the specialist letter; still outstanding. | documented | `06f891b08770…` |
| L0033 | eob:EOB-001 | 2026-09-15 | Claim CLM-2026-0915: MRI-LS-001 billed AUD 850.00; paid AUD 0.00; patient responsibility AUD 850.00 | documented | `fb987b44e0f8…` |
| L0034 | procedure_codes:MRI-LS-001 |  | MRI-LS-001: MRI lumbar spine without contrast; contrast=no; prior_auth=False; covered=True | reference | `1656a2a76269…` |
| L0035 | procedure_codes:MRI-LS-002 |  | MRI-LS-002: MRI lumbar spine with contrast; contrast=yes; prior_auth=True; covered=True | reference | `1dae3c1a26b8…` |
| L0036 | procedure_codes:MRI-LS-003 |  | MRI-LS-003: MRI lumbar spine with and without contrast; contrast=yes; prior_auth=True; covered=True | reference | `26846978bf2f…` |
| L0037 | procedure_codes:MRI-LS-004 |  | MRI-LS-004: CT lumbar spine; contrast=no; prior_auth=False; covered=True | reference | `0b7687321c15…` |
| L0038 | procedure_codes:MRI-LS-005 |  | MRI-LS-005: X-ray lumbar spine; contrast=no; prior_auth=False; covered=True | reference | `be6b0ead0327…` |
| L0039 | procedure_codes:SPINE-FUSION-001 |  | SPINE-FUSION-001: Investigational spinal fusion; contrast=no; prior_auth=True; covered=False | reference | `e97bc74e9408…` |
| L0040 | icd10_codes:M54.5 |  | M54.5: Low back pain, unspecified | reference | `f8af7c2a5582…` |
| L0041 | icd10_codes:M51.1 |  | M51.1: Lumbar and other intervertebral disc disorders with radiculopathy | reference | `9af899825360…` |
| L0042 | icd10_codes:M54.50 |  | M54.50: Low back pain, unspecified, site unspecified | reference | `c7ccca32eb66…` |
| L0043 | claim_documents:DOC-001 | 2026-08-12 | Imaging order: present | present | `e82949a2eb16…` |
| L0044 | claim_documents:DOC-002 | 2026-08-05 | Physiotherapy notes: present | present | `75ee32e01e33…` |
| L0045 | claim_documents:DOC-003 | 2026-08-20 | Specialist referral letter: missing | missing | `6ceda794281f…` |
| L0046 | claim_documents:DOC-004 | 2026-10-01 | Explanation of Benefits: present | present | `f81db984d8c8…` |
| L0047 | claim_documents:DOC-005 | 2026-09-20 | Clinical notes: present | present | `51442a3a84f4…` |

## Counterfactuals
| Removed source | Strength | Change | Reasons rebutted |
|---|---:|---:|---:|
| policy_clauses | 84 → 65 | -19 | 3 → 2 |
| medical_records | 84 → 65 | -19 | 3 → 2 |
| procedure_codes | 84 → 65 | -19 | 3 → 2 |
| eob | 84 → 84 | +0 | 3 → 3 |
| icd10_codes | 84 → 65 | -19 | 3 → 2 |

## Limitations
- This packet assembles evidence for human review. It is not medical or legal advice.
- It does not predict the insurer's decision; a human must review and sign it.
- No missing document has been fabricated.

## Provenance
SHA-256 chain over 47 evidence lines. Head `51442a3a84f4a5d43cf89254614758b9ae493fc17622539d51c18b1b34ee0ef6`. Any edit to an evidence line breaks the chain.
