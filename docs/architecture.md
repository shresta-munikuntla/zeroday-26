# SentinelAI — Architecture & System Design

Short version: **one backend, one database, one vector store, one LLM endpoint, five agents run in a fixed order, and a human approves before anything is sent.**

---

## 1. Component diagram

```text
┌──────────────────────┐   HTTPS + JWT    ┌──────────────────────────────────────────────────────────┐
│  React dashboard     │ ───────────────► │  FastAPI backend  (backend/api)                          │
│  (frontend/)         │ ◄─────────────── │   auth · role checks · Pydantic validation               │
│  list · detail ·     │      JSON        │                     │                                    │
│  approve / reject    │                  │                     ▼                                    │
└──────────────────────┘                  │  Orchestrator — Agent 4 (backend/workflow)               │
                                          │   IncidentState · validators · audit writer              │
                                          │     │         │          │             │                 │
                                          │     ▼         ▼          ▼             ▼                 │
                                          │  Agent 1 → Agent 2 → Agent 3 ──► Agent 5                 │
                                          │  detect    investigate  RAG         employees + drafts   │
                                          │     │         │          │             │                 │
                                          │     ▼         ▼          ▼             ▼                 │
                                          │  ┌─────── Tool layer (backend/tools) ───────┐            │
                                          │  │ predefined, parameterized query functions │           │
                                          │  └───────┬──────────────────────┬────────────┘           │
                                          │          ▼                      ▼                        │
                                          │   SQLite (exact records)   ChromaDB (documents)          │
                                          │                                                          │
                                          │  Nemotron client (backend/llm) ──► Brev endpoint         │
                                          │  Notification adapter (backend/notifications) ──► mock / │
                                          │                                                  Photon  │
                                          └──────────────────────────────────────────────────────────┘
```

Only the backend talks to Nemotron, Photon, or the database. The browser never sees API keys.

---

## 2. System design

### 2.1 Two data stores, different jobs

| Store | Holds | Queried by | Why |
|---|---|---|---|
| **SQLite** (via SQLAlchemy Core) | logs, accounts, permissions, assets, employees, teams, approved networks, maintenance windows, incidents, notifications, audit events | exact lookups: "events for admin_04 between 09:00 and 09:30" | Facts must be exact and verifiable by ID |
| **ChromaDB** | MITRE techniques, policies, past incidents (chunked by `##` section) | similarity search: "guidance for privileged login from unknown IP" | Guidance is found by meaning, not exact match |

Raw logs are **never** put in ChromaDB.

### 2.2 Tool layer (least privilege)

Agents never write SQL. They call fixed functions (spec §3.3), e.g. `get_account_permissions(account_id)`. Every function validates inputs, uses bound parameters, and returns only the fields needed.

| Agent | May read | May write |
|---|---|---|
| 1 Detection | logs, accounts, approved networks, maintenance windows | — |
| 2 Investigation | logs, permissions, assets | — |
| 3 Intelligence | investigation output, ChromaDB | — |
| 4 Orchestrator | all agent outputs | incidents, audit events |
| 5 Employee | final report, asset owners, minimal employee fields | notification drafts |

### 2.3 Shared workflow state

```python
class IncidentState(TypedDict):
    incident_id: str
    detection: dict | None        # Agent 1
    investigation: dict | None    # Agent 2
    intelligence: dict | None     # Agent 3
    employee_matches: list | None # Agent 5
    final_report: dict | None
    approval_status: str          # pending | approved | rejected
    notification_status: str      # not_sent | sent | failed | mocked
    errors: list                  # any step that failed or timed out
```

Agents pass **structured JSON** (contracts in spec §2), never whole datasets.

### 2.4 Incident lifecycle

```text
detected → investigating → awaiting_approval → notified → closed
                       └──► incomplete (a step failed; nothing is invented)
                                         └──► rejected (reviewer said no)
```

### 2.5 LLM usage

- One `NemotronClient`, shared by all agents. No per-agent model.
- **Rules decide, the LLM explains.** Detection, permission checks, severity, and recipient matching are deterministic Python. The LLM writes explanations and recommendation wording.
- Untrusted text (logs, documents) is wrapped in labelled delimiters; the system prompt says never follow instructions inside them.
- Every LLM response is parsed as JSON, validated against a Pydantic model, and every ID in it is checked against the database / retrieved set. Bad output → flagged, not used.
- If the endpoint is down, agents fall back to template text and the report says so.

### 2.6 Security boundaries

| Boundary | Control |
|---|---|
| Browser → API | JWT login, `reviewer` role required for approve / reject / send, enforced server-side |
| Agent → data | Tool layer only; no raw SQL, shell, or infrastructure access |
| Data → LLM | Delimited untrusted content; schema + ID validation of output |
| Report → recipient | Only active asset owners (allowlist from DB); each message contains only that recipient's asset |
| Send | Blocked unless `approval_status = approved`; one send per incident + recipient |
| Everything | Audit event per step; no secrets or unneeded personal data in logs |
| Infrastructure | **No automatic containment.** The system only recommends. |

### 2.7 API (spec §10)

`POST /api/auth/login` · `POST /api/incidents/run-demo` · `GET /api/incidents` · `GET /api/incidents/{id}` · `GET …/evidence` · `GET …/recipients` · `POST …/approve` · `POST …/reject` · `POST …/send` · `GET …/audit` · `GET /api/health` (only unauthenticated route).

---

## 3. End-to-end workflow (one click of "Run demo")

| # | Step | Owner | Output |
|---|---|---|---|
| 1 | Agent 1 runs rules over logs | P1 | detection JSON with `LOG-101…105` |
| 2 | Validate detection (schema, IDs exist) | P2 | pass / error |
| 3 | Agent 2 builds timeline, checks permissions, rates severity | P1 | investigation JSON, severity `high` |
| 4 | Validate investigation | P2 | pass / error |
| 5 | Agent 3 retrieves MITRE / policy / case chunks, drafts recommendations | P2 | intelligence JSON with doc IDs |
| 6 | Validate doc IDs, merge into final report, save incident | P2 | `final_report` |
| 7 | Agent 5 matches owners and drafts one message each | P3 | 3 drafts (EMP-001, 003, 006) |
| 8 | Status `awaiting_approval`; dashboard shows report + drafts | P3 | — |
| 9 | Reviewer approves → `send` → mock/Photon adapter | P3 | delivery result |
| 10 | Audit events written at every step | P2 | audit trail |

---

## 4. Team breakdown

| | **P1 — Data & Detection** | **P2 — AI & Workflow** | **P3 — People & Product** |
|---|---|---|---|
| Owner | @shresta-munikuntla | @Sadwitha11611 | @sathwika21n |
| Builds | DB schema + seed loader, tool layer, Agent 1, Agent 2 | repo skeleton, Nemotron client, RAG, Agent 3, validators, orchestrator, audit | employee queries, Agent 5, FastAPI, auth, notification adapter, dashboard |
| Folders | `backend/database`, `backend/tools`, `backend/agents/threat_detection.py`, `investigation.py` | `backend/llm`, `backend/rag`, `backend/agents/intelligence.py`, `backend/workflow`, `backend/security/audit.py` | `backend/agents/employee_notification.py`, `backend/api`, `backend/notifications`, `backend/security/auth.py`, `frontend/` |
| Provides to others | `detect()`, `investigate()`, query functions, **fixtures by Hour 4** | `NemotronClient`, `search_knowledge()`, `run_incident_workflow()` | `match_and_draft()`, API the UI calls |
| Consumes | `NemotronClient` (optional, P2) | P1 functions, P3 `match_and_draft()` | P2 `run_incident_workflow()`, P1 DB |

**Hand-off rule:** everyone works against **fixtures** (hand-written JSON matching the contracts) until the real component is ready. Swap the fixture for the real call when it lands.

---

## 5. Key decisions

| Decision | Choice | Reason |
|---|---|---|
| Database | SQLite through SQLAlchemy Core (`text()` + bound params), no ORM | Zero setup; `DATABASE_URL` can switch to Postgres later |
| Orchestration | Plain sequential Python first; LangGraph only if time allows | Fewer moving parts in 24 h; same state shape either way |
| Detection | Deterministic rules; LLM only explains | Repeatable, testable, can't be talked into a verdict |
| Severity | Deterministic rubric (POL-004 §1) | LLM may not raise or lower severity |
| Embeddings | `all-MiniLM-L6-v2`, local | Small, CPU-friendly |
| Chunking | One chunk per `##` section of each doc | Docs are short; sections map to citable references |
| Recipients | Active **owners** only; team channel if none; backups not notified | Minimum disclosure (POL-004 §2) |
| Notifications | Adapter interface, `mock` default; Photon only once its API is confirmed | Demo must work offline |
| Auth | JWT, roles `viewer` and `reviewer`, Argon2-hashed demo passwords from env | Approval must be a real permission check |
| Schema additions | `approved_networks`, `maintenance_windows`, `teams`, `notifications` | Needed for benign-explanation checks, team fallback, per-recipient delivery status |
| Data | Custom synthetic + official MITRE subset | See [datasets.md](datasets.md) |

## 6. Still open

| Question | Default until answered |
|---|---|
| Exact Brev / Nemotron base URL + model ID | Client runs in fallback mode |
| Which Photon product / API | Mock adapter |
| What "NMC" refers to | Generic data-center wording |
