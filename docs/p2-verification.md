# Issue #30 — P2 implementation and verification

Verified November 8, 2026. **Latest live verification: [runtime-check-results.md](runtime-check-results.md).** The production workflow uses the real repository P1
`detect()` / `investigate()` / existence queries and P3 `match_and_draft()`.
Fixture adapters are confined to tests and the explicitly labelled fixture demo.
No deployment, GPU provisioning, model installation, commit, or push was performed.

## What is implemented

- OpenAI-compatible Nemotron JSON client: configured endpoint/model/key, 30-second
  request timeout, one retry for transient failures, immediate fallback on an empty
  key, strict `json.loads`, and no provider prompt/credential logging.
- Reasoning handling: separate `reasoning_content` is ignored; reasoning mixed
  into final content, Markdown fences, and JSON substrings are rejected. No JSON
  repair or guessed fields. A reasoning-only response activates fallback.
- Untrusted source allowlist: `log`, `document` (legacy P1 label),
  `retrieved_document`, and `investigation`. IDs and content are XML-escaped;
  unknown labels or missing IDs fail before a request. The required never-follow
  system instruction is included verbatim.
- Deterministic Markdown ingestion, original metadata/sections, duplicate-heading
  IDs, configured MiniLM embeddings, persistent `knowledge` collection rebuild,
  and default fixture exclusion. Other collections are preserved.
- Filtered retrieval, deduplication, missing URL as `None`, exact document IDs,
  and score `1 / (1 + squared-L2 distance)` with cutoff **0.4**.
- Agent 3: three searches (MITRE 3, policies 3, cases 2), JSON/schema/citation
  validation, unsupported-reference removal, grounded source-only fallback, and
  explicit no-source result. It rejects model-added severity/recipient fields,
  injected email addresses, and unsupported identifiers in model prose.
- Native P1 detection/investigation and P3 draft validation, including nested
  timeline/permission IDs. Explicit compact service contracts remain for fixtures.
- Sequential orchestration, final-report validation, preserved intermediate state,
  incomplete/error handling, evidence-set deduplication, and pending human approval.
- Audit events for each stage, validation outcomes, retrieval IDs, model rejection,
  fallback, errors, and final status; sensitive details are excluded/redacted.
- API startup and POST `/api/incidents/run-demo` invoke the entire workflow.
  Replays preserve existing approval/delivery decisions. Incomplete reports cannot
  be approved. This workflow only drafts notifications; it does not send them.

## Executed checks

| Check | Result |
|---|---|
| Full suite with real local RAG enabled | **142 passed, no skips** in 10.77 s, including live Nemotron |
| Default unit/API suite | **132 passed, 5 skipped**; local RAG integrations and live API opt-in skipped |
| CLI `python -m backend.rag.ingest` | **11 documents, 38 chunks, 0 errors**, fixtures excluded |
| Fixture orchestrator CLI after ingestion | **1 INC-001**, awaiting_approval, no errors, repeated-run reuse, 14 audit events |
| Real Agent 2 → retrieval → Agent 3, no key | Required sources found; exact AI-unavailable limitation |
| Literal `chocolate cake recipe` | `[]` |
| Real poisoned index + real P1/P2/P3 | High severity, EMP-001/003/006, no email in state, no POL-099 action citation |
| Missing fields, malformed types, LOG-999/PERM-999 | Rejected; incomplete states and validation/error audits |
| P1 incident persistence | Native evidence key resolves INC-001; next allocator number is 2 |
| Compileall, pip check, git diff --check | Passed; no broken installed dependencies |
| `.env`, vector index/cache ignore checks | Passed |
| Live Brev API | **Passed** after opening the supplied Brev tunnel and fixing Nano v2 request formatting |
| Fresh network installation from a new clone | **Not repeated in this run**; requirements unchanged, installed environment checked |

The real incident query retrieved CASE-002, CASE-003, MITRE-T1078, MITRE-T1110,
POL-001, and POL-003, with retained chunk scores 0.4427–0.6201. These are actual
semantic search results, not a hardcoded document list. Earlier corpus calibration
found relevant distances 0.5474–1.1448 and unrelated nearest distances
1.8526–1.9559. Recalibrate the cutoff if corpus, model, or distance metric changes.

The first CLI fixture attempt overlapped an index rebuild and failed safely; it
passed when run after ingestion completed. Do not ingest concurrently with serving
retrieval: collection replacement is not an atomic online index swap.

## Exact local commands

Run from `zeroday-26/`. These installation commands are instructions, not a claim
that another fresh dependency installation was executed during this review.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

If `.env` does not already exist, copy `.env.example` to `.env`. Preserve an
existing local `.env`. Set local values there; never commit it.

```sh
python -m backend.rag.ingest
python -m pytest -q
SENTINELAI_RUN_RAG_INTEGRATION=1 python -m pytest -q
python -m backend.tests.run_fixture_workflow
python -m compileall -q backend tests
python -m pip check
```

The fixture CLI uses a temporary SQLite database and fake P1/P3; the automated
production integration tests use real P1/P3 with isolated seeded databases.
`pytest.ini` now discovers both `backend/tests` and `tests`.

The real local-RAG suite was executed using the already cached embedding model:

```sh
SENTINELAI_RUN_RAG_INTEGRATION=1 HF_HOME=/private/tmp/sentinelai-p2-huggingface HF_HUB_OFFLINE=1 MPLCONFIGDIR=/private/tmp/sentinelai-p2-matplotlib .venv/bin/python -m pytest backend/tests tests -q -o addopts=''
```

That machine-specific cache environment is optional. Normal first-time embedding
use downloads MiniLM and requires network access. It does not install a GPU model
or modify the Brev server.

## Mock and real Nemotron configuration

Mock mode requires no model server:

```dotenv
NEMOTRON_BASE_URL=
NEMOTRON_MODEL=
NEMOTRON_API_KEY=
EMBEDDING_MODEL=all-MiniLM-L6-v2
CHROMA_PERSIST_DIRECTORY=./data/chroma
```

An empty key always raises `LLMUnavailable`; Agent 3 reports
`AI summary unavailable; showing retrieved sources only.` If no source passes
retrieval, it also reports `No relevant source was retrieved.`

For the user's existing Brev vLLM deployment, first open a private SSH forward.
Replace `YOUR_BREV_SSH_ALIAS` with the existing SSH destination/alias supplied by
Brev and use its existing authentication configuration:

```sh
ssh -N -L 127.0.0.1:8000:127.0.0.1:8000 -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 YOUR_BREV_SSH_ALIAS
```

Keep that session running, and set local `.env`:

```dotenv
NEMOTRON_BASE_URL=http://127.0.0.1:8000/v1
NEMOTRON_MODEL=nvidia/NVIDIA-Nemotron-Nano-9B-v2
NEMOTRON_API_KEY=local-vllm
EMBEDDING_MODEL=all-MiniLM-L6-v2
CHROMA_PERSIST_DIRECTORY=./data/chroma
```

`local-vllm` is a non-secret SDK placeholder for the unauthenticated local-only
server. It does not secure or authenticate vLLM. The SSH tunnel provides access;
keep both listeners on loopback and leave the existing Brev deployment unchanged.

Verify actual inference explicitly:

```sh
NEMOTRON_RUN_LIVE=1 python -m pytest backend/tests/test_nemotron_live.py -q
```

This makes a real `chat_json` request and verifies a unique nonce; no fallback can
make the test pass. Failure means live integration remains unverified. Default
unit/API tests do not spend Brev credits, even when `.env` has real settings.

For a full local pipeline after ingestion:

```sh
python -c 'from backend.workflow.orchestrator import run_incident_workflow; print(run_incident_workflow())'
```

Use fresh isolated demo databases when checking live Agent 3: an existing incident
is deliberately reused and does not repeat inference. Do not reseed or delete a
shared database just to force a model call. FastAPI additionally requires locally
set `JWT_SECRET_KEY` (at least 32 characters), `DEMO_VIEWER_PASSWORD`, and
`DEMO_REVIEWER_PASSWORD`; these remain empty in the safe example.

## Files and integration boundaries

Created in the working tree: `backend/workflow/integration.py`,
`backend/tests/test_nemotron_live.py`.

Updated P2 runtime: `backend/config.py`, `backend/llm/nemotron_client.py`,
`backend/rag/{ingest,retrieve,vector_store}.py`,
`backend/agents/{intelligence,intelligence_contract}.py`,
`backend/workflow/{orchestrator,validators}.py`, `backend/security/audit.py`.
Existing `state.py`, `storage.py`, package initializers, and requirements already
supply the remaining deliverables and were retained.

Updated shared integration/configuration: `.env.example`, `.gitignore`,
`backend/main.py`, `backend/api/routes_incidents.py`, `pytest.ini`.
Updated tests: `backend/tests/{conftest,test_api,test_injection,test_workflow}.py`
and `tests/{test_ingest,test_intelligence,test_nemotron,test_retrieve}.py`.
Updated handoff documentation: this file and `docs/p2-contracts.md`.
The initial working tree already contained earlier uncommitted integration work;
these changes were preserved. P1/P3 agent algorithms and schemas were not replaced.

## Remaining limits

- No unavailable P1/P3 function dependencies remain on the default runtime path.
  The repository still has separate P1 and P3 SQLite stores. The adapter preserves
  both schemas, writes P1's native incident/evidence key for correct ID allocation,
  and stores API/state/report data through P3. This is not an atomic distributed
  transaction or a completed migration to the architecture's single SQLite store.
- Architecture ends at §6 and refers elsewhere to an unavailable spec. Sections
  8/9 and the complete external nested contracts/dependency list were not supplied.
  Models reflect the landed code and existing Agent 3 schema; exact compliance
  with unseen spec text cannot be certified.
- Live Brev JSON-mode compatibility needs the explicit opt-in test. A working GPU
  deployment reported by the user is distinct from a tested local SSH/API path.
- Citation/identifier checks prove provenance and metadata consistency, not that
  every generated sentence is semantically entailed by a source. Retrieved text
  remains untrusted; analyst review is required. No live-model injection-safety
  claim is made.
- Whole-detector failure is audited and raised without inventing an incident ID;
  per-incident failures preserve state as incomplete. Setup/database failures can
  prevent persistence and must be repaired by the caller.
- Existing incidents are reused, including incomplete ones; automatic retry,
  concurrent workflow execution, and online index swapping are not implemented.

## Latest local configuration check

The three previously blank Nemotron settings were populated only in the ignored,
untracked local `.env`, using the user's supplied deployment details:
`http://127.0.0.1:8000/v1`, `nvidia/NVIDIA-Nemotron-Nano-9B-v2`, and the non-secret
`local-vllm` placeholder. `.env.example` remains empty. No other local settings
were replaced. A `/v1/models` connectivity probe outside the sandbox returned
connection refused, so the tunnel must be started before live inference can be
verified. This is not evidence of a failed GPU deployment. The acceptance suite
was rerun afterward: 136 passed, 1 live API test intentionally skipped.

## Interactive judge demo

The dashboard now includes an accessible five-stage workflow explorer with
confirmed facts/evidence IDs, expandable cited policy/case/technique references,
and persisted audit events. Export report opens the browser print dialog.
Frontend API defaults to localhost:8001, leaving port 8000 for the model tunnel.

Reviewer-only buttons make explicit requests (no inference on page load):

- **Test Nemotron** calls POST `/api/ai/check`. It verifies an exact random nonce
  through actual JSON inference and shows model, latency, timestamp, and verified
  or unavailable status. Empty keys select fallback without an API request.
- **Generate AI preview** calls POST
  `/api/incidents/{id}/preview-intelligence`. It performs fresh RAG and output
  validation even for an existing rejected incident. It shows cited output and
  labels validated generation versus fallback. Preview does not save over the
  original report, change severity/approval, or rewrite/send notification drafts.
- The saved-report badge is based on persisted `ai_generation` provenance for new
  workflows. Older reports say generation was not recorded; a successful probe
  alone never marks an existing report as generated by Nemotron.

Both actions are audited, and the UI refreshes the audit after completion.
Checking the connection consumes a real model request when configured. The
separate preview consumes another request if relevant documents are found.

Verification: 140 backend tests passed with real local RAG enabled; one live API
test intentionally skipped. Two server-rendering frontend tests and Vite build
passed. No actual browser automation or live Brev inference was executed for
this frontend update. Keep the tunnel and backend running, restart Vite if
necessary, open localhost:5173, sign in as reviewer, and select INC-001.

## Live verification supersedes earlier connectivity limits

The later run established the Brev port forward, verified the served model ID,
passed the real nonce test and complete suite (142 passed, no skips), exercised
Chrome on desktop/mobile, and ran an isolated full real-agent workflow with
Nemotron-generated intelligence. See [the runtime report](runtime-check-results.md)
for exact commands, observed results, fixes, screenshots, and remaining limits.
Earlier “not executed” or “tunnel unavailable” statements above describe prior
checks, not the final runtime state.
