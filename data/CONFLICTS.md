# Planted conflicts and required behaviour

Four conflicts are seeded into the data. The Critic must find each one, the
Reconciler must re-query where evidence can settle it, and the Reporter must
carry the terminal state into the packet.

## Vocabulary

- **rebutted** — the evidence contradicts the insurer's reason; the rebuttal
  carries at least two citations.
- **missing** — a required document is genuinely absent. The packet is
  conditional; the document is added to the checklist and never fabricated.
- **open** — found, not yet settled.
- **unresolved** — still open after the loop caps and any escalation; it
  receives the 20-point deduction.

## C1 — the experimental clause is the wrong clause

**Planted evidence**

- `DEN-01`: "The service is experimental or investigational." It cites
  `POL-4.3`.
- `POL-4.3`: the experimental exclusion applies to `SPINE-FUSION-001` and
  states it **does not apply to diagnostic MRI of the lumbar spine**.
- `POL-4.1`: MRI-LS-001 is covered after at least six weeks of conservative
  therapy.

**Expected action**

1. The Critic compares the cited clause's `applies_to` with the file's actual
   procedure code (`MRI-LS-001`) and finds that the cited clause does not apply.
2. It issues a re-query for `POL-4.3` and `POL-4.1`.
3. The Reconciler rebuts DEN-01 with the two policy lines, the MRI order and
   the EOB.

**Terminal state:** rebutted. The packet quotes POL-4.3's own exclusion of
diagnostic MRI.

## C2 — the code and diagnosis in the denial are not the file's

**Planted evidence**

- `DEN-02` cites `MRI-LS-002` (with contrast) and diagnosis `M51.1`.
- The imaging order, EOB and record use `MRI-LS-001` (without contrast) and
  diagnosis `M54.5`.
- `POL-7.2` says MRI-LS-002 requires prior authorisation; MRI-LS-001 does not.
- The public ICD-10 descriptions resolve both codes: M51.1 is disc disorder
  with radiculopathy; M54.5 is low back pain.

**Expected action**

1. The Critic flags the code and diagnosis mismatch and issues a re-query for
   the two procedure codes.
2. It re-checks the live ICD-10 descriptions in adversarial review; the
   Advocate forces this re-query before the appeal can be accepted.
3. The Reconciler rebuts DEN-02 with both codes, the EOB, the order and both
   diagnosis descriptions.

**Terminal state:** rebutted. The packet says the insurer answered a denial for
a different code and diagnosis.

## C3 — the record documents conservative treatment

**Planted evidence**

- `DEN-03`: "No conservative treatment is documented."
- 12 physiotherapy sessions from 20 May to 5 August 2026.
- An NSAID trial on 10 June 2026.
- `POL-5.1` requires at least six weeks of conservative treatment.

**Expected action**

1. The Critic counts the physiotherapy sessions and weeks and compares them to
  `POL-5.1`.
2. It issues a re-query over the physiotherapy, GP review and physiotherapy
   review rows.
3. The Reconciler rebuts DEN-03 with the 12 sessions, the NSAID trial, the
   order and POL-5.1.

**Terminal state:** rebutted.

## C4 — the specialist referral letter is missing

**Planted evidence**

- `DEN-04`: "A specialist referral letter was not provided."
- `claim_documents.csv` DOC-003: status `missing`, requested 20 August 2026,
  note "Requested from the treating specialist; not received. Never fabricate."
- `POL-6.4` requires the letter.

**Expected action**

1. The Critic flags a missing required document. It does **not** assert that
  the reason is false.
2. It issues a re-query over the document checklist.
3. The Reconciler marks DEN-04 `missing`, adds DOC-003 to the checklist and
   sets the packet to `conditional`.
4. The score is capped at 84. The next-best action names the letter and the
   projected score of 100.

**Terminal state:** missing / conditional. The letter is never fabricated.

## Regression expectations

`tests/test_conflicts.py`, `tests/test_scorer.py`,
`tests/test_data_integrity.py` and `tests/test_provenance.py` assert:

- DEN-01/02/03 are `rebutted` with at least two citations;
- DEN-04 is `missing`, with DOC-003 in the checklist and no fabricated text;
- the score is 84 / solid / conditional, raw 90, cap 84;
- the counterfactuals for policy, records, codes and ICD-10 are negative; EOB
  is zero;
- the trace contains five re-queries, including `mark_missing` and
  `verify_diagnosis`;
- the hash chain verifies and tampering breaks it.
