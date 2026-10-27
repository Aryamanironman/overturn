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
| L0001 | policy_clauses:POL-10.1 | 2026-01-01 | POL-10.1 Definitions: A specialist referral letter is a letter from the treating specialist that recommends the imaging and is dated after the imaging order. | reference | `6f6d2325a3dc…` |
| L0002 | policy_clauses:POL-12.4 | 2026-01-01 | POL-12.4 Clinical records: Clinical records must be dated and attributable to a treating provider. | reference | `5b54f483faf1…` |
| L0003 | policy_clauses:POL-13.1 | 2026-01-01 | POL-13.1 Response time: The insurer must respond to an internal appeal within 30 days of receiving it. | reference | `07be175eb440…` |
| L0004 | policy_clauses:POL-4.1 | 2026-01-01 | POL-4.1 Covered imaging: MRI lumbar spine without contrast (MRI-LS-001) is covered when the member has completed at least six weeks of conservative therapy. | reference | `af78cd75127e…` |
| L0005 | policy_clauses:POL-4.2 | 2026-01-01 | POL-4.2 Prior authorisation: MRI lumbar spine without contrast (MRI-LS-001) does not require prior authorisation. Contrast studies (MRI-LS-002, MRI-LS-003) require prior authorisation. | reference | `78e00903ca9f…` |
| L0006 | policy_clauses:POL-4.3 | 2026-01-01 | POL-4.3 Experimental or investigational: The experimental exclusion applies to spinal fusion (SPINE-FUSION-001) and disc replacement. It does not apply to diagnostic MRI of the lumbar spine. | reference | `325038afcf44…` |
| L0007 | policy_clauses:POL-5.1 | 2026-01-01 | POL-5.1 Medical necessity: Lumbar imaging is medically necessary when the clinical record documents failed conservative treatment for at least six weeks, including physiotherapy or analgesic medication. | reference | `7bba71a2d338…` |
| L0008 | policy_clauses:POL-5.2 | 2026-01-01 | POL-5.2 Conservative therapy: Conservative therapy includes physiotherapy, a structured home exercise programme and analgesic medication. | reference | `4d65ae099ef0…` |
| L0009 | policy_clauses:POL-6.4 | 2026-01-01 | POL-6.4 Claim documentation: An imaging claim must include a specialist referral letter dated after the imaging order. Without it the claim is incomplete. | reference | `eb3b4e1fc907…` |
| L0010 | policy_clauses:POL-7.2 | 2026-01-01 | POL-7.2 Claim edits: Procedure code MRI-LS-002 (MRI with contrast) requires prior authorisation. MRI-LS-001 (without contrast) does not. | reference | `4bc9ead49c58…` |
| L0011 | policy_clauses:POL-8.1 | 2026-01-01 | POL-8.1 Internal appeal: A member may request an internal appeal within 60 days of the denial date. | reference | `51b2a73ac452…` |
| L0012 | policy_clauses:POL-9.3 | 2026-01-01 | POL-9.3 Policy version: Version 2026.1 is effective 1 January 2026 and supersedes version 2025.3. | reference | `f4b74b4806a2…` |
| L0013 | medical_records:REC-001 | 2026-05-12 | GP consultation 2026-05-12: Low back pain, no red flags; referred to physiotherapy. | documented | `6f83b0ed1e34…` |
| L0014 | medical_records:REC-002 | 2026-05-20 | Physiotherapy 2026-05-20: Physiotherapy session 1 of 12; home exercise programme. | documented | `42ccef91652b…` |
| L0015 | medical_records:REC-003 | 2026-05-27 | Physiotherapy 2026-05-27: Physiotherapy session 2 of 12; home exercise programme. | documented | `20c1cc40d597…` |
| L0016 | medical_records:REC-004 | 2026-06-03 | Physiotherapy 2026-06-03: Physiotherapy session 3 of 12; home exercise programme. | documented | `caac5c6303cd…` |
| L0017 | medical_records:REC-005 | 2026-06-10 | GP review 2026-06-10: NSAID trial commenced; continue physiotherapy. | documented | `b7c8db40909d…` |
| L0018 | medical_records:REC-006 | 2026-06-10 | Physiotherapy 2026-06-10: Physiotherapy session 4 of 12; home exercise programme. | documented | `422cfd6bd99f…` |
| L0019 | medical_records:REC-007 | 2026-06-17 | Physiotherapy 2026-06-17: Physiotherapy session 5 of 12; home exercise programme. | documented | `81e2db243457…` |
| L0020 | medical_records:REC-008 | 2026-06-24 | Physiotherapy 2026-06-24: Physiotherapy session 6 of 12; home exercise programme. | documented | `905743b27a3a…` |
| L0021 | medical_records:REC-009 | 2026-07-01 | Physiotherapy 2026-07-01: Physiotherapy session 7 of 12; home exercise programme. | documented | `0c77224232f4…` |
| L0022 | medical_records:REC-010 | 2026-07-01 | Physiotherapy review 2026-07-01: Progress review; continue programme. | documented | `60c069dddee7…` |
| L0023 | medical_records:REC-011 | 2026-07-08 | Physiotherapy 2026-07-08: Physiotherapy session 8 of 12; home exercise programme. | documented | `96cb339a9277…` |
| L0024 | medical_records:REC-012 | 2026-07-15 | Physiotherapy 2026-07-15: Physiotherapy session 9 of 12; home exercise programme. | documented | `e51e9b7c5a60…` |
| L0025 | medical_records:REC-013 | 2026-07-22 | Physiotherapy 2026-07-22: Physiotherapy session 10 of 12; home exercise programme. | documented | `ef6fecc7ec4c…` |
| L0026 | medical_records:REC-014 | 2026-07-29 | Physiotherapy 2026-07-29: Physiotherapy session 11 of 12; home exercise programme. | documented | `9414a3d39489…` |
| L0027 | medical_records:REC-015 | 2026-08-05 | Physiotherapy 2026-08-05: Physiotherapy session 12 of 12; home exercise programme. | documented | `d6c3506ab83b…` |
| L0028 | medical_records:REC-016 | 2026-08-12 | GP consultation 2026-08-12: Twelve weeks of conservative therapy completed; MRI requested; specialist referral requested. | documented | `828626a8ba14…` |
| L0029 | medical_records:REC-017 | 2026-08-20 | Specialist administration 2026-08-20: Referral letter requested from the specialist; not received. | documented | `a1812a26ee46…` |
| L0030 | medical_records:REC-018 | 2026-09-02 | Claims administration 2026-09-02: Claim submitted for MRI-LS-001. | documented | `4a578f841385…` |
| L0031 | medical_records:REC-019 | 2026-09-15 | Imaging service 2026-09-15: MRI lumbar spine without contrast performed. | documented | `31527aee039e…` |
| L0032 | medical_records:REC-020 | 2026-09-20 | Specialist administration 2026-09-20: Second request for the specialist letter; still outstanding. | documented | `00f91ada4bb9…` |
| L0033 | eob:EOB-001 | 2026-09-15 | Claim CLM-2026-0915: MRI-LS-001 billed AUD 850.00; paid AUD 0.00; patient responsibility AUD 850.00 | documented | `f5fa210b5a1b…` |
| L0034 | procedure_codes:MRI-LS-001 |  | MRI-LS-001: MRI lumbar spine without contrast; contrast=no; prior_auth=False; covered=True | reference | `8570a3e47261…` |
| L0035 | procedure_codes:MRI-LS-002 |  | MRI-LS-002: MRI lumbar spine with contrast; contrast=yes; prior_auth=True; covered=True | reference | `a10a9a28af38…` |
| L0036 | procedure_codes:MRI-LS-003 |  | MRI-LS-003: MRI lumbar spine with and without contrast; contrast=yes; prior_auth=True; covered=True | reference | `210ae726ec95…` |
| L0037 | procedure_codes:MRI-LS-004 |  | MRI-LS-004: CT lumbar spine; contrast=no; prior_auth=False; covered=True | reference | `4b6e9d71b287…` |
| L0038 | procedure_codes:MRI-LS-005 |  | MRI-LS-005: X-ray lumbar spine; contrast=no; prior_auth=False; covered=True | reference | `d875b66d1406…` |
| L0039 | procedure_codes:SPINE-FUSION-001 |  | SPINE-FUSION-001: Investigational spinal fusion; contrast=no; prior_auth=True; covered=False | reference | `c2c3a1c099c9…` |
| L0040 | icd10_codes:M54.5 |  | M54.5: Low back pain, unspecified | reference | `ad34f3d924d9…` |
| L0041 | icd10_codes:M51.1 |  | M51.1: Lumbar and other intervertebral disc disorders with radiculopathy | reference | `a520a3b40a09…` |
| L0042 | icd10_codes:M54.50 |  | M54.50: Low back pain, unspecified, site unspecified | reference | `a36f65e9b491…` |
| L0043 | claim_documents:DOC-001 | 2026-08-12 | Imaging order: present | present | `cd1ffa652f85…` |
| L0044 | claim_documents:DOC-002 | 2026-08-05 | Physiotherapy notes: present | present | `47b7af8eb603…` |
| L0045 | claim_documents:DOC-003 | 2026-08-20 | Specialist referral letter: missing | missing | `b9fe98ea943d…` |
| L0046 | claim_documents:DOC-004 | 2026-10-01 | Explanation of Benefits: present | present | `a80725780c54…` |
| L0047 | claim_documents:DOC-005 | 2026-09-20 | Clinical notes: present | present | `387f5f91b90a…` |

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
SHA-256 chain over 47 evidence lines. Head `387f5f91b90accb1a05a07853cf345e04862c8cd1c10e011a00f48c7dae98b11`. Any edit to an evidence line breaks the chain.
