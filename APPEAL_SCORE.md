# Appeal strength

The appeal strength is deterministic Python (`overturn/scorer.py`). No LLM
reads, writes or adjusts it. It measures the **file**, not the insurer's
decision.

## Formula

Start at **100**.

| Deduction / bonus | Points | Counts as |
|---|---:|---|
| Unresolved denial reason | −20 each | status `open` or `unresolved` after the caps and any escalation |
| Missing required document | −15 each | a denial reason classified `missing` |
| Unsupported rebuttal | −10 each | a `rebutted` reason with fewer than two citations |
| Stale evidence | −5 each | a cited clinical record or EOB older than 180 days |
| All non-missing reasons rebutted with two citations | +5, once | the bonus is lost if any non-missing reason is unresolved |

**Cap:** if any required document is missing, the final score is
`min(raw, 84)`. A file with a missing required document cannot be "strong".
Clamp to **0–100**.

### Buckets

| Score | Bucket |
|---:|---|
| 85–100 | strong |
| 70–84 | solid |
| 55–69 | partial |
| below 55 | weak |

### Status

- `ready` — no unresolved reason, no missing document, no unsupported rebuttal.
- `conditional` — a required document is missing; the packet says exactly which.
- `draft` — a reason remains unresolved or unsupported.

## Worked example — Ava, as of 2026-10-24

| Item | Count | Points |
|---|---:|---:|
| Unresolved reasons | 0 | 0 |
| Missing document (Specialist referral letter, DOC-003) | 1 | −15 |
| Unsupported rebuttals | 0 | 0 |
| Stale evidence (records May–Aug 2026; within 180 days) | 0 | 0 |
| All three non-missing reasons rebutted with ≥2 citations | — | +5 |

```
100 − 15 + 5 = 90  →  capped at 84 because DOC-003 is missing
84 / 100 — solid — conditional
```

Supplying DOC-003 removes the cap: **100 / 100 — strong — ready**.

## Counterfactuals

After scoring, the pipeline removes each evidence source in turn and
recomputes. A rebuttal depends on a source type:

| Finding kind | Depends on |
|---|---|
| wrong_clause | `policy_clauses` |
| code_mismatch | `procedure_codes` and `icd10_codes` |
| medical_necessity | `medical_records` |
| missing_document | `claim_documents` |

When a dependency is removed, the reason becomes unresolved in the
counterfactual; the score and the "reasons rebutted" count are recomputed.
The EOB is corroborating evidence, not a required dependency, so removing it
does not change Ava's score. The packet reports both the score delta and the
rebutted-count delta.

## Why these rules

- **Unresolved reasons** are the core risk: the appeal does not answer the
  insurer.
- **Missing documents** are a hard completeness condition. The cap prevents a
  polished packet from claiming "strong" while a required attachment is absent.
- **Unsupported rebuttals** are assertions without evidence; two citations
  force the agent to point at the policy, the record or the code.
- **Stale evidence** is excluded from the score's confidence even if it is
  corroborated.
- **The +5** rewards a complete, multi-source rebuttal of every non-missing
  reason.

## What this score is not

It is not a probability that the insurer will overturn the denial. It is not
medical or legal advice. It is an evidence-strength measure for a human
reviewer. The packet states this in its limitations section.

## Reproducing

```bash
python -m overturn.run --case ava --out out/
python -m pytest tests/test_scorer.py tests/test_provenance.py -q
```

`tests/test_scorer.py` hand-computes the 84/conditional result, the 100/ready
result after the missing document is supplied, the unresolved deduction and
the bucket boundaries. `tests/test_provenance.py` recomputes the packet's score
from its own emitted reasons and evidence.
