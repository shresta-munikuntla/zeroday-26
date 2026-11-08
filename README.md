# SentinelAI

**An AI-assisted security investigation copilot for data-center teams.** Built for HackUTD 2026 (24-hour hackathon).

SentinelAI reads security logs, spots suspicious activity, works out what it might affect, looks up relevant security guidance, and drafts a clear alert for **the specific person responsible** for the affected servers. A human approves the alert before it is sent. Nothing is ever changed on infrastructure automatically.

> **Status:** early build. The synthetic dataset and knowledge base are in place (`data/`). Backend, agents, and dashboard are tracked as GitHub Issues.

---

## The problem

Security alerts are often cryptic: *"unusual login on admin_04."* Whoever reads it still has to figure out:

- What exactly happened, and is it actually bad?
- Which servers are involved, and how important are they?
- What does our policy say to do?
- **Who** owns those servers and needs to know?

## What SentinelAI does

Walk-through of the demo scenario (all data is fictional):

1. An admin account logs in on a **Saturday** from an IP address it has never used and that isn't the company VPN.
2. Within 8 minutes it reaches three servers — one it is allowed on, one whose permission **expired last month**, and a critical database it was **never** allowed on (denied twice).
3. SentinelAI flags this, builds a timeline, and checks permissions.
4. It retrieves the matching **MITRE ATT&CK** techniques, company policy, and a similar past incident.
5. It drafts **three separate alerts** — one per server owner — each explaining *why you're getting this* and *what to check next*, citing exact log IDs.
6. A security lead approves; the alerts are sent (or recorded by a mock sender).

It also shows restraint: an admin logging in through the **approved VPN**, a user **mistyping a password** three times, and the **nightly backup job** touching every server are all left alone.

---

## How it works

```text
            security logs, accounts, permissions, assets        policies, MITRE, past incidents
                          (SQLite)                                      (ChromaDB)
                             │                                               │
 ┌───────────────────────────┼───────────────────────────────────────────────┼──────────┐
 │  Orchestrator (Agent 4) — runs each step, validates output, records an audit trail   │
 │                           ▼                                               ▼          │
 │  Agent 1 Detection ──► Agent 2 Investigation ──► Agent 3 Intelligence (RAG)          │
 │  "what looks wrong"    "what happened, what's     "what guidance applies"            │
 │                         affected, how sure"                                          │
 │                                          ──► Agent 5 Employee & Notification         │
 │                                              "who needs to know, and what to say"    │
 └──────────────────────────────────────────────────────────────┬───────────────────────┘
                                                                ▼
                                       Human approval in dashboard ──► Photon / mock sender
```

| Agent | Job | Key rule |
|---|---|---|
| **1 · Threat Detection** | Finds suspicious events with deterministic rules (unfamiliar IP, failed-login bursts, unauthorized access, unusual timing) | The LLM explains; it never decides alone |
| **2 · Investigation** | Builds the timeline, checks permissions, separates facts from hypotheses, rates severity | Never claims compromise or data theft without evidence |
| **3 · Intelligence (RAG)** | Retrieves MITRE techniques, policies, past cases; recommends next steps | Every recommendation cites a source document |
| **4 · Orchestrator** | Runs agents in order, validates every evidence ID, handles failures | Marks gaps as incomplete — never fills them in |
| **5 · Employee & Notification** | Matches affected assets to their owners and drafts a tailored message for each | Only owners are notified; each sees only their own asset |

### Design principles

- **Evidence-led** — every claim points to a log ID (`LOG-103`), permission (`PERM-003`), or document (`POL-002`), and those IDs are checked against the database.
- **Human in the loop** — the system recommends; people decide. No automatic account disabling, IP blocking, or config changes.
- **Logs are untrusted** — text inside logs or documents is treated as data, never as instructions (the dataset includes a prompt-injection attempt to prove it).
- **Least privilege** — agents call a small set of predefined backend functions, never raw SQL or a shell.

---

## Tech stack

| Layer | Technology | Why |
|---|---|---|
| LLM | **NVIDIA Nemotron** on **Brev**, via the OpenAI-compatible `openai` client | One shared model endpoint for all agents |
| Orchestration | **LangGraph** (or plain sequential Python) | Ordered workflow with shared state |
| Backend API | **FastAPI** + **Pydantic** + Uvicorn | Typed request validation, async |
| Database | **SQLite** (Python's built-in `sqlite3`) | Zero-setup single source of truth, nothing to install |
| RAG | **ChromaDB** + **sentence-transformers** (`all-MiniLM-L6-v2`) | Local vector search over policies and MITRE data |
| Auth & security | **PyJWT**, **pwdlib[argon2]**, slowapi (rate limiting) | Login, role checks, hashed passwords |
| Frontend | **React** + axios + react-router | Incident dashboard and approval screen |
| Notifications | **Photon** adapter, with a **mock** fallback | Works offline for the demo |
| Quality | pytest, ruff, pip-audit | Tests, linting, dependency audit |
| Language | Python 3.11+, JavaScript | |

---

## Repository layout

```text
zeroday-26/
├── data/                         ✅ ready
│   ├── seed/                     synthetic logs, accounts, permissions, assets, employees + test ground truth
│   ├── knowledge/                RAG documents: MITRE subset, policies, past incidents, injection test doc
│   ├── scripts/                  generate_seed.py, extract_mitre.py
│   └── README.md                 what each file is for and why it exists
├── backend/                      🚧 planned — FastAPI app, agents, workflow, RAG, notifications, auth
├── frontend/                     🚧 planned — React dashboard
└── docs/
    ├── architecture.md           ✅ architecture, system design, workflow, team breakdown, key decisions
    └── datasets.md               ✅ how the datasets were built and why
```

**New here?** Read this README → [docs/architecture.md](docs/architecture.md) → [docs/datasets.md](docs/datasets.md) → your issue.

## The data (all fictional)

| What | Size | Notes |
|---|---|---|
| Security logs | 157 events, Nov 4–7 2026 | Normal weekday baseline + one attack scenario + three look-alike benign cases + one prompt-injection log |
| Assets | 8 | Web servers, bastion host, identity server, critical customer DB, management network |
| Accounts / permissions | 5 / 20 | Includes one **expired** permission that the attacker still uses |
| Employees | 8 | Fictional names; one asset deliberately has no active owner to test fallback routing |
| Knowledge base | 4 MITRE techniques, 4 policies, 3 past incidents | MITRE content is official (ATT&CK v20.1); everything else is written for the demo |

IPs come from reserved documentation ranges (RFC 5737), so no real address appears anywhere. Ground-truth answers for tests are in `data/seed/scenario_manifest.json`. See **[data/README.md](data/README.md)** for full details.

---

## Getting started

Right now only the dataset can be regenerated:

```bash
git clone https://github.com/shresta-munikuntla/zeroday-26.git
cd zeroday-26
python -I data/scripts/generate_seed.py      # rebuilds data/seed/ (deterministic)
```

Backend and frontend setup instructions will be added here as those components land. Configuration will live in a local `.env` (copied from `.env.example`) — **never commit real keys**.

## Team and ownership

| Area | Owns | Owner |
|---|---|---|
| Data & Detection | Dataset, database, Agent 1, Agent 2 | [@shresta-munikuntla](https://github.com/shresta-munikuntla) |
| AI & Workflow | Nemotron client, RAG, Agent 3, Agent 4, audit log | [@Sadwitha11611](https://github.com/Sadwitha11611) |
| People & Product | Agent 5, API, auth, dashboard, notifications | [@sathwika21n](https://github.com/sathwika21n) |

Work is tracked in **[GitHub Issues](https://github.com/shresta-munikuntla/zeroday-26/issues)** — one issue per person (P1, P2, P3), each with step-by-step tasks, acceptance criteria, and deliverables. How the three parts connect: [docs/architecture.md §4](docs/architecture.md#4-team-breakdown).

### Build plan (24 hours)

| Hours | Milestone |
|---|---|
| 0–1 | Agree on schemas and agent contracts |
| 1–4 | Database, model client, employee mapping, API skeleton — every component has a working stub |
| 4–12 | Agents 1–3, orchestrator, notification drafts |
| 12–19 | End-to-end workflow, dashboard, approval, audit log |
| 19–24 | Edge-case testing, polish, demo rehearsal |

**If behind schedule:** keep one complete end-to-end incident. Cut extra scenarios and visuals before cutting evidence checks, employee matching, or human approval.

---

## Attribution

MITRE ATT&CK® content © The MITRE Corporation, used under the [ATT&CK Terms of Use](https://attack.mitre.org/resources/legal-and-branding/terms-of-use/).
