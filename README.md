# OVERTURN

**The denial, answered with evidence.**

OVERTURN reads a health-insurance denial, the policy it cites, the clinical record, the EOB, the code tables and the document checklist. It finds the contradiction, re-queries the source, and drafts an internal appeal packet a human can send.

The case in this repository: **Ava, 34, Sydney.** Northbridge Health denied claim **CLM-2026-0915** for **MRI-LS-001** (MRI lumbar spine without contrast). The denial gives four reasons. Three are contradicted by the file. The fourth is a specialist referral letter that is genuinely missing — and OVERTURN will not invent it.

Result: **84 / 100 — solid — conditional.** Supply the one missing letter and the packet becomes **100 / ready**.

---

## Film

A **76-second marketing-pitch film**, built with the huashu-motion method: one
paused GSAP timeline, `window.seek(t)`, the skill's fonts, and its signature.

- `video/out/overturn-film.mp4` — 1920 × 1080, 30 fps, H.264/AAC, 76 s
- `video/out/overturn-film.gif` — opening 8 s, 640 px
- `video/out/overturn-poster.png` — frame 0
- `out/overturn-film.mp4` — convenience copy
- `video/share.md` — the post and the licence note

Narration is **The Podcaster** (VoiceStudio / OmniVoice; young Australian
woman, high pitch), generated locally. The 120 BPM bed ducks under the voice.
The film shows the four reasons, the agent loop, the missing letter and the
84 → 100 next action. The OmniVoice weights are non-commercial; see
`THIRD_PARTY.md`.

Rebuild:

```bash
python video/make_voice.py      # VoiceStudio TTS + scene timings
python video/make_score.py      # 120 BPM bed + voice mix
python video/render_film.py --frames
# encode with FFmpeg (see video/share.md)
```

The film is a pitch, not the required 1–4 minute workflow demo; the demo still
needs a screen recording of the live system.

---

## Run it

Fresh clone, no credentials, no Zetaris, no Nightshift:

```bash
python -m overturn.run --case ava --out out/
```

This runs the whole pipeline in `SAMPLE_MODE` in about one second.

Outputs:

- `out/appeal_packet.md` — the packet a human reviews and sends
- `out/appeal_packet.json` — the same packet, machine-readable
- `out/receipt.html` — the evidence map
- `out/trace.jsonl` — every hop, SQL query, model and decision

Tests:

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

**36 tests pass.** They include the live Zetaris REST contract against a local HTTP double, the Nightshift headers/model-discovery contract, the Meterless adapter paths, both loop caps, the four conflicts, the score, the hash chain and the offline end-to-end run.

---

## The loop

```
Scout / Intake ──► Planner ──► Reconciler ──► Critic.conflict_check
                                    ▲              │
                                    └── re-query ──┘   (max 4 iterations)
                                                   │
                         Critic.adversarial_review + Advocate
                                    ▲              │
                                    └── re-query ──┘   (max 3 iterations)
                                                   │
                         unresolved after cap? ──► one human question
                                                   │
                         Scorer ──► Reporter ──► appeal packet
```

- The **Reconciler is the only agent that calls `run_sql`.** The Critic issues a precise re-query; the Reconciler executes it and mutates the shared case.
- Both loops are bounded. Every hop is in `trace.jsonl` before the next step.
- The **appeal strength score is deterministic Python**; no LLM touches it.
- The **Advocate is pinned to the Nemotron lane** when `NEMOTRON_MODEL` is set. The trace logs both the requested and the **served** model.

The five agents:

| Agent | Job | Lane |
|---|---|---|
| Planner | decomposes the request, selects sources, emits the plan | `MODEL_PLANNER` |
| Reconciler | the only `run_sql` caller; builds the evidence ledger | `MODEL_RECONCILER` |
| Critic | `conflict_check` and `adversarial_review` | **Nemotron** |
| Advocate | argues the insurer's side; tries to break the appeal | **Nemotron** |
| Reporter | drafts the cover letter and reason-by-reason rebuttal from computed facts | `MODEL_REPORTER` |

---

## The four planted conflicts

See `data/CONFLICTS.md` for the exact expected states.

| # | Conflict | Terminal state |
|---|---|---|
| C1 | DEN-01 cites POL-4.3, the experimental exclusion — which by its own text does not apply to diagnostic MRI. | **rebutted**: POL-4.3 applies to spinal fusion; POL-4.1 covers MRI-LS-001 after six weeks. |
| C2 | DEN-02 cites MRI-LS-002 (with contrast) and diagnosis M51.1; the order, EOB and record use MRI-LS-001 and M54.5. | **rebutted**: the contrast code required prior authorisation; the file's code does not. |
| C3 | DEN-03 says no conservative treatment is documented. | **rebutted**: 12 physiotherapy sessions over 12 weeks plus an NSAID trial. |
| C4 | DEN-04 says the specialist referral letter is missing. | **missing / conditional**: the letter is genuinely absent; it is added to the checklist, never fabricated. |

The loop performs **five re-queries**: one per denial reason, plus a live ICD-10 re-check forced by the Advocate when the diagnosis code in the denial differs from the record.

---

## Why the score is 84, not 100

The full formula is in `APPEAL_SCORE.md`.

```
100 − 0 unresolved − 15 missing + 5 all-supported = 90
capped at 84 because a required document is missing
```

The cap is deliberate. An appeal with a missing required document is not "strong"; it is **solid and conditional**. The next-best-action names the document and the projected score:

> Obtain Specialist referral letter (DOC-003). Supplying it raises the appeal strength from 84 to 100 and makes the packet ready.

Counterfactual provenance is a headline feature:

| Removed source | Strength | Change |
|---|---:|---:|
| policy clauses | 84 → 65 | −19 |
| clinical record | 84 → 65 | −19 |
| procedure codes | 84 → 65 | −19 |
| live ICD-10 descriptions | 84 → 65 | −19 |
| EOB | 84 → 84 | 0 |

Removing the EOB leaves the code/record argument intact, so the score does not move. That is honest, not a bug.

---

## Sponsor technology

| Sponsor | Where it is load-bearing |
|---|---|
| **Zetaris** | The only data path. Policy clauses, denial reasons, clinical records, EOB, procedure codes, document checklist and ICD-10 descriptions are registered as tables/views; `run_sql` is the single data tool. `scripts/register_zetaris_sources.sql` has the registration, semantic view and smoke queries. |
| **Meterless World Model** | Holds the shared case: evidence lines, denial reasons, missing documents and the packet. The Reconciler writes; the Critic reads; `tests/test_meterless_adapters.py` exercises the adapter. |
| **Meterless H-MEM** | Remembers the claimant's appeal pattern and the insurer's denial pattern. Run two recalls run one (`tests/test_hmem.py`). |
| **Meterless Scout Intent** | The deterministic router selects denial appeal, billing error or prior auth before any agent runs. |
| **Meterless Nightshift** | The primary AI provider. `llm.py` implements the OpenAI-compatible contract with `meterless-app` and `meterless-scope` headers, `/v1/models` discovery and served-model logging. |
| **NVIDIA Nemotron** | The Critic and Advocate share the pinned Nemotron lane. The Advocate's strongest move — the live ICD-10 re-check — is a Nemotron-class reasoning task, not a generic chat call. The trace shows the served model. |

The live contract tests use local HTTP doubles so they run with no credentials:

- `tests/test_zetaris_client.py` asserts the exact path, `Authorization`, `X-Org-ID`, UUID `X-Request-ID`, `{"sql","limit"}` body and row extraction.
- `tests/test_nightshift_client.py` asserts `meterless-app`, `meterless-scope`, model discovery, the selected Nemotron model and the served model in the trace.
- `tests/test_meterless_adapters.py` asserts the World Model and H-MEM HTTP calls.

**Live verification is pending the Zetaris platform bundle and Nightshift credentials.** SAMPLE_MODE is fully verified. The live adapters are written to the current contracts from the Zetaris getting-started repository and the participant setup guide.

---

## Live setup

`.env.example` contains placeholders only.

```bash
# Zetaris local UI-proxy install
ZETARIS_REST_URL=http://localhost:3000
ZETARIS_ORG_ID=1
ZETARIS_API_KEY=...
ZETARIS_SQL_PATH=/api/proxy/sql-editor/sqls/run-query

# Nightshift
METERLESS_BASE_URL=http://127.0.0.1:8088/v1
METERLESS_RUNTIME_TOKEN=...
METERLESS_APP=overturn
METERLESS_SCOPE=user
NEMOTRON_MODEL=nvidia/nemotron-3.5-super-vl-120b-a12b
```

Then:

```bash
cp .env.example .env      # fill in, never commit
python -m overturn.run --case ava --out out/ --live
```

Register the sources in Zetaris with `scripts/register_zetaris_sources.sql`. The CSV files must be in storage Zetaris can reach (an S3/MinIO bucket; not a laptop path). The SQL uses `s3a://overturn/...` and marks the options to confirm with the deployed Zetaris version.

---

## Security and limits

- No secrets in the repository. `.env` is gitignored; `.env.example` has placeholders only. The NVIDIA key belongs in Nightshift's Providers tab, not in this project.
- `run_sql` rejects writes, DDL and multi-statement SQL before it reaches any database.
- The case is **synthetic**: no real patient, insurer, provider, claim or PHI. The denial, policy, records and codes are generated deterministically.
- This packet assembles evidence for **human review**. It is not medical or legal advice and does not predict the insurer's decision. A human must review and sign it.
- A missing required document is never fabricated. The packet says what to send.
- The marketing film uses VoiceStudio's OmniVoice engine, whose weights are **non-commercial** (CC-BY-NC and related terms). The film is a non-commercial hackathon demo; the model licence is recorded in `THIRD_PARTY.md`. Do not reuse the narration commercially without checking the model terms.

---

## Repository map

```
overturn/
  run.py            CLI, control loop, hard caps, escalation
  router.py         denial_appeal / billing_error / prior_auth classifier
  planner.py        agent
  reconciler.py     the only run_sql caller; builds the evidence ledger
  critic.py         conflict detectors + adversarial review
  advocate.py       insurer's voice; Nemotron lane
  reporter.py       packet, rebuttal annex, SHA-256 chain
  scorer.py         deterministic appeal strength + counterfactuals
  world_model.py    shared case (Meterless adapter + local)
  hmem.py           cross-session memory (Meterless adapter + local)
  llm.py            Nightshift client, discovery, served-model logging
  zetaris.py        read-only run_sql transport (Zetaris / SQLite mirror)
  trace.py          JSONL tracer
  prompts.py        all agent prompts
  receipt.py        evidence-map receipt
scripts/
  generate_sources.py           deterministic synthetic sources
  build_sample_db.py            CSV + JSON -> SQLite mirror
  register_zetaris_sources.sql  tables, live ICD-10 REST, semantic view, smoke queries
data/
  sources/          policy, denial, records, EOB, codes, documents, ICD-10
  fixtures/         sample.db, ICD-10 cache, escalation answers
  README.md         source, licence, subset, row counts, registration
  CONFLICTS.md      the four planted conflicts and their terminal states
tests/              36 tests
input_examples/     ava_request.json
output_examples/    a committed sample run
APPEAL_SCORE.md     the deterministic score and counterfactual rules
```

---

## Submission checklist

- [x] One worker, one denial, one decision, one packet.
- [x] Five agents with critique, re-query, shared state and bounded loops.
- [x] Deterministic appeal strength + counterfactual provenance.
- [x] Source-cited packet with a SHA-256 provenance chain.
- [x] SAMPLE_MODE runs with no Zetaris, Nightshift or credentials.
- [x] Zetaris and Nightshift contract tests.
- [x] Meterless World Model + H-MEM feature tests.
- [x] No secrets; `.env.example` placeholders only.
- [ ] Live Zetaris + Nightshift run (pending the platform bundle and credentials).
- [ ] 1–4 minute demo video, slide deck and public GitHub repository.
- [ ] The missing specialist letter is supplied for a 100/ready packet (the product tells the human exactly what to send).
