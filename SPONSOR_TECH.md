# Sponsor technology explanation — OVERTURN

OVERTURN reads a health-insurance denial, re-queries the policy, clinical record, EOB, procedure-code table, document checklist and ICD-10 descriptions, and drafts an evidence-backed internal appeal packet. The case in this repository is Ava, 34, Sydney, claim **CLM-2026-0915**, procedure **MRI-LS-001**. The packet scores **84/100 — solid — conditional**: three denial reasons are rebutted, and the fourth is a specialist referral letter (DOC-003) that is genuinely missing and is never fabricated.

This document explains the five required sponsor-technology points. It separates what is **verified in this repository** from what is **wired for live use but requires live credentials**. The repository contains no `.env` and no live credentials, and no live Zetaris, Nightshift, Meterless-engine or NVIDIA-Nemotron run has been performed here.

## Verification status

### Verified in this repository

- **37 tests pass.** Observed with `python -m pytest -q`: `37 passed` (37 collected). The suite includes the live REST contracts against local HTTP doubles, the Meterless adapter HTTP paths, the Zetaris USL/data-quality views, both loop caps, the four planted conflicts, the score, the hash chain and the offline end-to-end run.
- **SAMPLE_MODE end to end.** `python -m overturn.run --case ava --out out/` builds `appeal_packet.json`, `appeal_packet.md`, `receipt.html` and `trace.jsonl` with no Zetaris, Nightshift or credentials. `tests/test_e2e_sample_mode.py::test_cli_runs_offline_and_writes_a_computed_packet` asserts the 84/conditional packet, four denial reasons, five re-queries and a valid hash chain.
- **Read-only SQL enforcement and the SQLite mirror.** `tests/test_zetaris_client.py::test_live_sql_contract` and `tests/test_zetaris_client.py::test_extract_rows_shapes`.
- **World Model and H-MEM feature behaviour.** `tests/test_world_model.py::test_critic_sees_reconciler_write`, `tests/test_hmem.py::test_second_run_recalls_first` and `tests/test_meterless_adapters.py::test_meterless_adapters_write_case_state_and_recall`.
- **Nightshift contract and served-model logging.** `tests/test_nightshift_client.py::test_nightshift_headers_discovery_and_served_model`.
- **The committed `out/` artifacts are SAMPLE_MODE outputs.** `out/appeal_packet.json` has `model_routing` set to `offline-deterministic` for all five agents; `out/trace.jsonl` records 14 SQL events with `engine: "sqlite-mirror"` and 9 `agent_call` events with `mode: "offline"`.

### Requires live credentials (written but not run here)

- A deployed **Zetaris** instance, an org id and an API key (or username/password), and the source CSVs in an S3/MinIO bucket reachable by Zetaris.
- A **Meterless Nightshift** base URL and Runtime token, plus a real model id from the Nightshift model picker.
- A real **H-MEM** and/or **World Model** engine URL and key, if those adapters are used instead of their local mirrors.
- An actual **NVIDIA Nemotron** model served through Nightshift. The repository has no NVIDIA SDK, CUDA, NIM or GPU code; NVIDIA enters only as the model lane behind Nightshift.

The live adapters are written to the contracts in the Zetaris getting-started repository and the participant setup guide. The tests that exercise them use local HTTP doubles, not the real services.

---

## 1. How Zetaris was integrated

### One data path, one tool

Zetaris is the only data path. Every source the agents can read is a Zetaris table or view, and the agents have exactly one data tool: `run_sql` in `overturn/zetaris.py`.

The architecture enforces this narrowly:

- `overturn/reconciler.py` is the only module that calls `run_sql` (lines 46, 100 and 369). `overturn/run.py` constructs the `SqlClient` and hands it to the Reconciler; no other agent receives a database handle.
- The Planner selects sources and emits SQL, but does not execute it. `overturn/planner.py` restricts the plan to `ALLOWED_SOURCES` — the seven source tables plus `appeal_evidence` and `claim_facts`.
- The Critic and Advocate propose a precise re-query; the Reconciler executes it. This is why the evidence ledger and the trace have a single SQL author.

`validate_read_only` in `overturn/zetaris.py` runs before either backend is reached. It strips leading comments, rejects an empty query, rejects more than one statement, accepts only a first token of `SELECT`, `WITH` or `EXPLAIN`, and rejects a forbidden keyword list that includes `INSERT`, `UPDATE`, `DELETE`, `DROP`, `CREATE`, `ALTER`, `ATTACH`, `DETACH`, `PRAGMA`, `VACUUM`, `REPLACE`, `TRUNCATE`, `GRANT` and `REVOKE`.

In live mode, `SqlClient._run_zetaris` sends:

```
POST {ZETARIS_REST_URL}{ZETARIS_SQL_PATH}
Authorization: Bearer <API key>
X-Org-ID: <numeric org id>
X-Request-ID: <fresh UUID>
{"sql": "...", "limit": 1000}
```

The default local UI-proxy path is `/api/proxy/sql-editor/sqls/run-query`; the legacy REST path is `/sql-editor/sqls/run` on port 8888. `extract_rows` accepts the several Zetaris response envelopes (rows with columns, nested `data`/`results`/`result`/`records`/`items`, or a bare list).

In SAMPLE_MODE, `SqlClient._run_sqlite` runs the same validated SQL against `data/fixtures/sample.db`, opened read-only with SQLite URI mode `mode=ro`. `scripts/build_sample_db.py` creates the same seven table names and the same two view names as the live registration script, so the SQL is portable between modes.

### The seven registered source tables

`scripts/register_zetaris_sources.sql` registers the seven file-backed Lightning tables (`CREATE LIGHTNING FILESTORE TABLE ... FORMAT CSV`) from `s3a://overturn/...`:

| Table | Rows | What it holds |
|---|---:|---|
| `policy_clauses` | 12 | The clauses the denial cites, and the clauses that actually apply |
| `denial_reasons` | 4 | DEN-01 to DEN-04, with cited clause, code, diagnosis and deadline |
| `medical_records` | 20 | Dated GP, physiotherapy and administration notes; 12 physiotherapy sessions |
| `eob` | 1 | EOB-001: MRI-LS-001, billed AUD 850, paid AUD 0 |
| `procedure_codes` | 6 | MRI-LS-001/002/003/004/005 and SPINE-FUSION-001, with contrast and prior-auth flags |
| `claim_documents` | 5 | DOC-001 to DOC-005; DOC-003 is `missing` |
| `icd10_codes` | 3 | Cached public ICD-10-CM descriptions for M54.5, M51.1 and M54.50 |

The same script adds:

- Two live REST tables, `icd10_m545` and `icd10_m511`, against the public no-key Clinical Tables ICD-10 endpoint, plus `CACHE TABLE` statements. These are the live-connectivity proof; the deterministic pipeline itself reads the cached `icd10_codes` table (see the precision note at the end).
- Two semantic views: `appeal_evidence` joins denial, policy, procedure code and diagnosis; `claim_facts` computes the maximum therapy weeks, physiotherapy-session count, ordered procedure code, recorded diagnosis code and missing-document count.
- Smoke queries for the four planted conflicts and the row-count check (expected 12, 4, 20, 1, 6, 5, 3).

The SQL comments are explicit that the table names, columns and view semantics are final, while the S3/MinIO `PATH` and connector option names must be confirmed against the deployed Zetaris version. The CSV files must be in storage Zetaris can reach; a laptop path is not visible to it. The two live REST tables use the literal header `user-agent "OVERTURN hackathon you@example.invalid"`; replace it with a real app name and contact before running them.

### The Unified Semantic Layer

The `overturn` schemastore container and three views form the USL:

- `usl_claim_review` — one row per denial reason, attributed to the cited policy clause and its text, the procedure code with its contrast/prior-auth flags, the diagnosis description, and the claim facts.
- `appeal_evidence` — the evidence-level join across denial, policy, procedure code and diagnosis.
- `claim_facts` — the claim measures: physiotherapy sessions, weeks of therapy, ordered and recorded codes, missing-document count.

`dq_claim_integrity` adds five data-quality rules (orphan clause, unknown code, undated record, fabricated missing document, disagreeing missing count), one row per rule with a failure count and a pass/fail status. Section 6 of the SQL file has two verification queries for each of the seven sources. `ZETARIS_USL.md` maps all five Zetaris evaluation criteria to these artefacts, and `tests/test_usl_views.py` runs the shipped `usl_claim_review` and `dq_claim_integrity` SQL against the SQLite mirror.

### Test showing it works

`tests/test_zetaris_client.py::test_live_sql_contract` starts a local `ThreadingHTTPServer` double and asserts the exact path, the expected Bearer value on `Authorization`, `X-Org-ID`, a parseable UUID `X-Request-ID`, the exact body `{"sql": "SELECT 1 AS one", "limit": 1000}`, and row extraction to `[{"one": 1}]`. `test_extract_rows_shapes` covers the response envelopes. These are contract tests against a double; they do **not** prove a live Zetaris deployment.

**Verified here:** the read-only validator, the SQLite mirror path, the execution flow, and the HTTP contract against a local double. **Requires live credentials:** the real Zetaris endpoint, the S3/MinIO registration, and the `register_zetaris_sources.sql` run itself.

---

## 2. Which Meterless engines were implemented

Two Meterless engine adapters are implemented: **H-MEM** and the **World Model**. Each has a local implementation used in SAMPLE_MODE and an adapter that mirrors to the engine when a URL is configured.

### H-MEM — cross-run case memory

**What it does in this product.** H-MEM remembers the claimant's appeal pattern and the insurer's denial pattern across runs. Before planning, `overturn/run.py` recalls memories for the case and passes them to the Planner. After the packet is written, it records two new memories:

- `appeal_pattern`: e.g. "3 of 4 reasons rebutted, 1 missing document; appeal strength 84 (solid, conditional)".
- `insurer_pattern`: the insurer's denial pattern by reason and finding kind.

**Exact code path.** `overturn/run.py`:

- `make_hmem(settings, tracer)` at line 275.
- `hmem.recall(case["case_id"], topics=["appeal", "denial", "insurer", "pattern"])` at line 276; the result is logged as `memory_recall`.
- `planner.run(case, route, memory)` at line 292; memory is part of the planning context.
- `_remember_run(hmem, case, world, score, tracer)` at line 351, which calls `hmem.remember` twice (lines 100 and 101).

`overturn/hmem.py` provides `LocalHMem`, a JSON mirror at `settings.hmem_path` (default `.overturn/hmem.json`), with `remember` and `recall`. `MeterlessHMem` subclasses it and posts to `{HMEM_URL}/v1/memories` on write and `{HMEM_URL}/v1/memories/recall` on read, with an optional bearer key. The local mirror remains authoritative for the run, so a network failure does not lose the run's memories. `make_hmem` selects the Meterless adapter only when `not settings.offline and settings.hmem_url`.

**Test showing it works.** `tests/test_hmem.py::test_second_run_recalls_first` runs the whole pipeline twice with the same local H-MEM store. Run 1 recalls nothing. Run 2 recalls prior items whose kinds include `appeal_pattern` and `insurer_pattern`, and whose text contains `appeal strength 84` and `Northbridge Health denial pattern`.

`tests/test_meterless_adapters.py::test_meterless_adapters_write_case_state_and_recall` additionally starts a local HTTP double, forces `offline=False` and `hmem_url`, asserts `hmem.engine == "meterless-hmem"`, and asserts that `/v1/memories` and `/v1/memories/recall` were called. The double returns no remote memories, so this test proves the HTTP calls and the local recall path, not a real engine's cross-session storage.

**Verified here:** the two-run recall behaviour and the adapter HTTP calls against a double. **Requires live credentials:** a real `HMEM_URL` engine; the endpoint shape is implemented but not confirmed against a deployed service.

### World Model — the shared case ledger

**What it does in this product.** The World Model is the one object the Reconciler and Critic both read and mutate. It holds:

- the evidence lines (`L0001`–`L0047`, one per source row);
- removed lines and exclusions;
- the denial conflicts (`CF-001`–`CF-004`);
- the computed claim facts, including `procedure_code`, `diagnosis_code`, `missing_documents` and `conditional`.

The Reconciler writes the evidence ledger, the claim and the four conflicts. The Critic reads the same ledger in `conflict_check`, decides which findings are evidence-backed, and writes the re-query SQL and action back onto the conflict. The Advocate reads the same state to construct the insurer's attacks. This shared state, rather than message passing, is what lets the adversarial loop operate on exactly the evidence the Reconciler gathered.

**Exact code path.**

- `overturn/run.py` line 285: `make_world_model(settings, tracer, case["case_id"])`.
- `overturn/world_model.py`: `LocalWorldModel` implements `reset`, `add_line`, `update_line`, `remove_line`, `add_conflict`, `update_conflict`, `add_exclusion`, `set_claim` and `snapshot`; `MeterlessWorldModel` subclasses it and posts the whole snapshot to `{WORLD_MODEL_URL}/v1/cases/{case_id}/state` after every line add/update/remove.
- `overturn/reconciler.py::reconcile` (lines 43–93) reads the Planner's queries, calls `run_sql`, builds the 47 lines, calls `world.add_line` for each, calls `world.set_claim`, and adds the four conflicts.
- `overturn/critic.py::conflict_check` (lines 52–120) reads `world.lines()` and `world.conflicts()`, then calls `world.update_conflict` with `requery_sql` and `action`.
- `overturn/advocate.py::review` reads `compute_stats(world)` and the claim.

**Test showing it works.** `tests/test_world_model.py::test_critic_sees_reconciler_write` asserts that the Reconciler writes exactly **47 evidence lines** (12 policy + 20 records + 1 EOB + 6 code + 3 ICD-10 + 5 documents), that the Critic finds four findings with kinds `wrong_clause`, `code_mismatch`, `medical_necessity` and `missing_document`, that every finding citation is a real line the Reconciler wrote, that DOC-003 is `missing`, and that DEN-01's action is `rebut_reason` with `POL-4.3` in its re-query. It also writes to a line after the Critic's read and asserts the next read sees the update.

`tests/test_meterless_adapters.py::test_meterless_adapters_write_case_state_and_recall` asserts that the Meterless adapter posts the case snapshot to `/v1/cases/ava/state`, with `case_id == "ava"` and the added line's `source_row_id == "DOC-003"`.

**Verified here:** the shared-ledger behaviour in SAMPLE_MODE and the adapter's HTTP payload against a double. **Requires live credentials:** a real `WORLD_MODEL_URL`; `overturn/world_model.py` itself says the engine's exact REST shape must be confirmed against the participant setup guide.

### Scope note: the router is not a Meterless engine adapter

`overturn/router.py::route_request` is deterministic Python. It classifies a request as `denial_appeal`, `billing_error` or `prior_auth` before any agent runs, using case hints and keyword matching, and sets the policy (appeal window, stale days, penalties, missing-document cap). The four tests in `tests/test_router.py` cover the three classes and the default. The README's sponsor table labels this "Meterless Scout Intent", but there is no Scout Intent HTTP adapter in the repository. I do not claim a Meterless Scout Intent integration; the two Meterless engines actually integrated are H-MEM and the World Model.

---

## 3. How the app connects to Meterless Nightshift

`overturn/llm.py` implements an OpenAI-compatible Nightshift client.

### Wire contract

- Base URL: `METERLESS_BASE_URL` (or `NIGHTSHIFT_BASE_URL`), normalised to end in `/v1` by `overturn/config.py::_nightshift_base`.
- Headers on both discovery and completion:

```
Authorization: Bearer <Runtime token>
meterless-app: <METERLESS_APP, default "overturn">
meterless-scope: <METERLESS_SCOPE, default "user">
```

- Model discovery: `GET {base}/models`, parsing either `{"data": [{"id": ...}]}` or a bare list. `available_models` logs a `model_discovery` event.
- Completion: `POST {base}/chat/completions` with `model`, `messages`, `temperature: 0.2` and `response_format: {"type": "json_object"}`. If the endpoint rejects `response_format` with HTTP 400, the client retries without it. It retries 429/500/502/503/504 up to three attempts, then raises `LLMError`.
- The served model is read from the response's `model` field, falling back to the requested model.

### Per-agent routing and served-model logging

The routing table is built in `overturn/config.py::load_settings`:

| Agent | Configuration | SAMPLE_MODE label |
|---|---|---|
| Planner | `MODEL_PLANNER` or `METERLESS_MODEL` or `meterless/auto` | `offline-deterministic` |
| Reconciler | `MODEL_RECONCILER` or fallback | `offline-deterministic` |
| Critic | `NEMOTRON_MODEL` if set, else `MODEL_CRITIC` or fallback | `offline-deterministic` |
| Advocate | `NEMOTRON_MODEL` if set, else `MODEL_ADVOCATE` or fallback | `offline-deterministic` |
| Reporter | `MODEL_REPORTER` or fallback | `offline-deterministic` |

If `NEMOTRON_MODEL` is set, `load_settings` forcibly assigns it to both `critic` and `advocate` (lines 153–155). `LLMClient.resolve_model` also checks it first. If the requested model is an alias (`""`, `auto`, `meterless/auto`, `unset`) and a live discovery is available, the Critic and Advocate prefer the first discovered model whose id contains `nemotron`; otherwise the client takes the first discovered model.

Every completion writes an `agent_call` trace event with `mode`, `model` (the served model), `requested_model`, `input_digest`, `latency_ms`, `decision` and `iteration`. The Reporter places the routing table in the packet as `model_routing`. The packet therefore records the configured route; the trace records the model that actually handled each request. This is the "logs the model that handled every request" requirement.

### SAMPLE_MODE labelling

In SAMPLE_MODE, `LLMClient.routing_table()` returns `offline-deterministic` for all five agents, and `complete()` sets both `requested_model` and `served_model` to `offline-deterministic` with `mode: "offline"`. The committed `out/appeal_packet.json` confirms this: its entire `model_routing` object is `offline-deterministic`. The committed `out/trace.jsonl` has 9 `agent_call` events (4 Critic, 2 Advocate, 1 Planner, 1 Reconciler, 1 Reporter), all with `mode: "offline"` and `model: "offline-deterministic"`. No network request to Nightshift is made in SAMPLE_MODE.

### Test showing it works

`tests/test_nightshift_client.py::test_nightshift_headers_discovery_and_served_model` starts a local HTTP double that serves `/v1/models` with `other-model` and `nvidia/nemotron-test`, and `/v1/chat/completions` with `{"model": "nvidia/nemotron-test", ...}`. It asserts:

- the POST goes to `/v1/chat/completions`;
- the expected Bearer value on `Authorization`, `meterless-app: overturn`, `meterless-scope: user`;
- the body model is `nvidia/nemotron-test`;
- the trace's `agent_call` has `model == "nvidia/nemotron-test"` and `mode == "live"`.

This proves the client contract against a double. It does **not** prove a real Nightshift deployment, model catalog or token.

**Verified here:** header construction, discovery parsing, request shape, model selection and served-model logging, all against a local double. **Requires live credentials:** a real `METERLESS_BASE_URL` and `METERLESS_RUNTIME_TOKEN`, a real `/v1/models` catalog and a real completion.

---

## 4. Where NVIDIA technology contributes

NVIDIA contributes through the **Nemotron model lane on Nightshift**, used for the two adversarial agents:

- **Critic** (`overturn/critic.py`): `conflict_check` and `adversarial_review`. The Critic must compare the denial's cited clause, code and diagnosis with the file, count the conservative treatment, notice that DOC-003 is missing, and then attack the appeal it has just supported.
- **Advocate** (`overturn/advocate.py`): argues the insurer's side, tries to break the appeal, and can force a diagnosis-code re-query when the denial and the record use different ICD-10 codes.

`overturn/config.py` pins both agents to `NEMOTRON_MODEL` when that variable is set, and `overturn/llm.py::resolve_model` uses the same pin. The `.env.example` value is `nvidia/nemotron-3.5-super-vl-120b-a12b`; the accompanying comment says to use the exact model id from Nightshift's model picker, so this is a placeholder for the deployment, not a verified served model.

**Why those two agents.** These are the only two places where model judgment can change the outcome. The Planner's output is normalised against a default plan; the Reconciler executes validated read-only SQL and builds the ledger; the Reporter's prose is checked for unsupported numbers and quotes and falls back to the computed annex if it fails. The Critic and Advocate, by contrast, must generate and evaluate arguments: does the cited clause actually apply, is the code/diagnosis mismatch real, does the record prove conservative treatment, can the missing letter be turned into a reason to reject the appeal? That is the reasoning-heavy part of the workflow, so it is the part routed to a Nemotron-class model.

**What is not in the repository.** There is no NVIDIA SDK import, no CUDA, no TensorRT, no NIM deployment and no GPU code. The only NVIDIA-specific artifacts are the `NEMOTRON_MODEL` setting and the routing logic. The repository also contains no measured Nemotron output: the committed sample run uses the offline deterministic functions, and the Nightshift contract test uses a local double with the synthetic id `nvidia/nemotron-test`, not the `.env.example` id.

**Verified here:** the pinning and routing logic, and served-model logging through the Nightshift double. **Requires live credentials:** an actual NVIDIA Nemotron model served by Nightshift; no live Nemotron call was made.

---

## 5. What was unique about the use of the sponsor technologies

1. **An adversarial verification loop that cannot be talked out of the evidence.** The Critic's deterministic detectors produce findings, the model reviews them, and then `overturn/critic.py` takes the union of the model-confirmed indices and **all** evidence-backed findings. A model dismissal is logged (`dismissed_by_model`) but cannot remove a contradiction the evidence supports. The loop is bounded: `MAX_CONFLICT_ITERS = 4`, `MAX_ADVOCATE_ITERS = 3`, one human escalation (`overturn/run.py`). `tests/test_control_loop.py::test_conflict_loop_caps_and_escalates_once` and `tests/test_control_loop.py::test_adversarial_loop_caps` cover the caps. This is the product's core use of Nightshift/Nemotron: the model is an adversary and a reviewer, not an oracle.

2. **Source-cited clause, code and record rebuttals.** Every rebutted reason carries line ids that resolve to a source row. `overturn/reconciler.py::_rebut_reason` refuses a rebuttal with fewer than two citations. The packet turns each into `source_table:source_row_id`. The three rebutted reasons are checked by `tests/test_conflicts.py::test_wrong_clause_cites_the_right_policy`, `::test_code_and_diagnosis_mismatch` and `::test_conservative_treatment_is_documented` (the last asserts 12 physiotherapy citations). The Zetaris single-data-path design is what makes this citation chain complete.

3. **Counterfactual source-removal scoring.** `overturn/scorer.py::counterfactuals` removes each of five evidence sources in turn, re-scores the appeal and re-evaluates which rebuttals survive. The committed packet shows: policy clauses 84 → 65 (−19), clinical records 84 → 65 (−19), procedure codes 84 → 65 (−19), ICD-10 descriptions 84 → 65 (−19), and EOB 84 → 84 (0). The EOB result is deliberately honest: removing the insurer's own claim record leaves the code/record argument intact. `tests/test_provenance.py::test_counterfactuals_cover_evidence_sources` and `tests/test_conflicts.py::test_counterfactuals_are_meaningful` assert the coverage and the signs.

4. **A tamper-evident SHA-256 hash chain over 47 evidence lines.** `overturn/reporter.py::hash_chain` sorts the lines by `line_id`, hashes `previous_hash + "|" + canonical_json(payload)` with SHA-256, and records `prev_hash` and `hash` on each line. The genesis value is 64 zeros; the head hash is in `packet["provenance"]`. `tests/test_provenance.py::test_hash_chain_verifies_and_detects_tampering` verifies the chain, edits one summary, and asserts verification fails. The committed packet's provenance block reports `algorithm: "sha256-chain-v1"`, `line_count: 47` and a head hash.

5. **A refusal to fabricate the missing document.** DOC-003 is `missing` in `claim_documents`, and the Reconciler's `_mark_missing` adds an exclusion with the reason "required document missing; do not fabricate". The score is capped at 84, the status is `conditional`, and the next-best action names the letter and projects 84 → 100. `tests/test_conflicts.py::test_missing_letter_is_never_fabricated` and `tests/test_provenance.py::test_missing_document_stays_missing` assert the missing state, the `not been fabricated` language and the next action. This is the clearest expression of the product's stance: an evidence system must know what it does not have.

Supporting all five is a deterministic scorer (`overturn/scorer.py`) that no LLM touches. `tests/test_scorer.py::test_hand_computed_score` recomputes the 90 raw, 84 cap, 84 score, `solid` bucket and `conditional` status by hand.

---

## Test map

| Test | What it proves |
|---|---|
| `tests/test_zetaris_client.py::test_live_sql_contract` | Exact live Zetaris POST path, headers, UUID request id, `{"sql","limit"}` body and row extraction, against a local double |
| `tests/test_zetaris_client.py::test_extract_rows_shapes` | The supported Zetaris response envelopes |
| `tests/test_nightshift_client.py::test_nightshift_headers_discovery_and_served_model` | Nightshift headers, `/v1/models` discovery, selected model, served model in the trace, against a local double |
| `tests/test_meterless_adapters.py::test_meterless_adapters_write_case_state_and_recall` | World Model and H-MEM adapters make the expected HTTP calls (`/v1/cases/ava/state`, `/v1/memories`, `/v1/memories/recall`) |
| `tests/test_hmem.py::test_second_run_recalls_first` | H-MEM actually persists across runs: run 2 recalls run 1's appeal and insurer patterns |
| `tests/test_world_model.py::test_critic_sees_reconciler_write` | The shared ledger: 47 lines written by the Reconciler, four findings read by the Critic, citations resolve, later writes are visible |
| `tests/test_provenance.py::test_hash_chain_verifies_and_detects_tampering` | The SHA-256 chain verifies and tampering breaks it |
| `tests/test_conflicts.py::test_trace_shows_real_requeries` | Five re-queries, including `mark_missing` and `verify_diagnosis` |
| `tests/test_e2e_sample_mode.py::test_cli_runs_offline_and_writes_a_computed_packet` | Fresh-clone SAMPLE_MODE run: 84/conditional, four reasons, five re-queries, valid chain, no key strings in outputs |

## Reproduce

```bash
python -m pip install -r requirements.txt
python -m pytest -q
# observed: 37 passed

python -m overturn.run --case ava --out out/
# SAMPLE_MODE, no credentials
```

The live command is available but was not run here:

```bash
cp .env.example .env
# fill in ZETARIS_*, METERLESS_*, NEMOTRON_MODEL; optionally HMEM_URL and WORLD_MODEL_URL
python -m overturn.run --case ava --out out/ --live
```

`config.py` refuses `SAMPLE_MODE=false` when the Zetaris REST URL/key and the Nightshift base URL/token are not configured, so an accidental empty live run fails fast rather than silently falling back.

## Precision notes where the code and the README differ

These are recorded so the submission does not overclaim:

- **"Meterless Scout Intent" is not an engine adapter in this repository.** `overturn/router.py` is deterministic local Python. The README's sponsor table uses the Meterless name, but there is no Scout Intent HTTP client, URL setting or test. The two Meterless engines implemented as adapters are H-MEM and the World Model.
- **The fifth re-query is not against the public ICD-10 REST endpoint.** The README calls it a "live ICD-10 re-check"; the actual SQL is `SELECT * FROM icd10_codes WHERE code IN ('M51.1', 'M54.5')`, and `icd10_codes` is the cached CSV table registered in `scripts/register_zetaris_sources.sql`. The live REST tables `icd10_m545` and `icd10_m511` are registered for connectivity but are not queried by the pipeline. The trace label says "live ICD-10 descriptions verified", which describes the intent, not the table actually read.
- **The packet's `model_routing` records configured routes, not necessarily the served model.** `LLMClient.routing_table()` returns `model_for(agent)`; `resolve_model()` and the response `model` field determine what actually served the request. The trace's `agent_call` events are the authoritative record of the served model.
- **The committed `out/` run is SAMPLE_MODE.** Its `model_routing` is entirely `offline-deterministic` and its SQL engine is `sqlite-mirror`. No live Zetaris, Nightshift, H-MEM, World Model or Nemotron call is represented in the committed artifacts.
- **The five-requery count and the 84 score are SAMPLE_MODE values.** `tests/test_conflicts.py::test_trace_shows_real_requeries` asserts five re-queries for the deterministic run. The deterministic scorer will produce the same score from the same conflict states, but live Critic/Advocate model output could change how many adversarial re-queries are issued (the four conflict-loop re-queries are driven by the deterministic detectors).
