# Provisional P2 contracts and configuration

These placeholders were explicitly authorized in chat while Agents 1 and 2 are
unfinished. They are development interfaces, **not a transcription of spec §2**.
No existing P1/P3 interfaces were changed. Reconcile them with the official spec
and P1/P3 before wiring the Orchestrator.

## Investigation input

`backend.agents.intelligence.analyze(investigation: dict) -> dict`

| Field | Provisional type | Meaning |
|---|---|---|
| status | string | Investigation status; `investigation_status` alias accepted |
| confirmed_facts | list of strings or objects | P1-confirmed evidence only |
| investigation_reasons | list of strings | Reasons; `reasons` alias accepted |
| additional fields | any JSON data | Preserved as untrusted input to the model |

Missing required fields or incorrect types raise Pydantic ValidationError before
retrieval or model calls. The sample in `tests/fixtures/investigation_placeholder.json`
is explicitly synthetic P2 test input derived from the documented scenario,
not output from an implemented Agent 2. Runtime code never loads that fixture or
the scenario manifest.

## Intelligence output

All six fields are required. All list items have `source_document_ids: list[str]`.
Unknown output fields are rejected.

| Field | Item fields besides source_document_ids |
|---|---|
| matched_techniques | technique_id: str, name: str, relevance: str |
| policy_references | policy_id: str, section: str, summary: str |
| historical_cases | case_id: str, summary: str, relevance: str |
| recommended_actions | action: str |
| recommended_resources | title: str, url: str |
| limitations | strings (no citation field) |

Citations must refer to retrieved documents. Entries with no valid supporting
citations are dropped, and limitations explain removal. Technique IDs, policy
IDs/sections, case IDs, and resource URLs are checked against retrieved metadata.
No test-fixture source or POL-099 is accepted as authority.

The model is instructed to distinguish guidance/historical context from current
facts. Schema, IDs, metadata, and URLs are checked deterministically; arbitrary
natural-language semantic correctness is not proved by those checks. A conservative
data-transfer-language check rejects the model output rather than accepting an
unsupported exfiltration claim. Mocked tests do not establish live model behavior.

All fallback responses contain:

`AI summary unavailable; showing retrieved sources only`

An empty retrieval additionally contains:

`No relevant source was retrieved.`

Fallback copies policy/case text, MITRE titles/IDs, and URLs from retrieval only;
it recommends reviewing the cited sections and explicitly qualifies applicability.
Retrieval can include distractors (T1110/CASE-003); a retrieved entry is guidance,
not a finding that the technique occurred. No action is executed.

## Development dependencies and configuration

`requirements.txt` pins the locally exercised P2 dependencies. It is explicitly
provisional because the exact spec §8 list is unavailable. It does not replace
P1/P3 dependency requirements.

| Setting | Default | Origin |
|---|---|---|
| NEMOTRON_BASE_URL | empty | Genuine Brev endpoint not provided |
| NEMOTRON_API_KEY | empty | No credentials supplied; immediate LLMUnavailable |
| NEMOTRON_MODEL | empty | Genuine deployment model ID not provided |
| EMBEDDING_MODEL | all-MiniLM-L6-v2 | Architecture |
| CHROMA_PERSIST_DIRECTORY | .cache/chroma | User-authorized local default |

`.env.example` keeps all five values empty. Blank embedding/storage settings use
the defaults above. `.cache/chroma` and `.env` are already ignored. No working
endpoint, key, or model identifier was fabricated.

## Workflow contracts and missing integrations (Steps 5–8)

The repository still contains no spec §2, P1/P3 implementation, SQLite schema,
DB helper, or agreed evidence-query module. The workflow therefore requires
explicit bindings rather than importing guessed P1 helper paths or using fakes
in production. The user-directed sqlite3 implementation takes precedence over
the architecture document's older SQLAlchemy wording. No SQLAlchemy dependency
was added.

Provisional models in `backend/workflow/validators.py`:

| Agent | Provisional output |
|---|---|
| 1 detect() | list of objects with incident_id: str (INC-digits), evidence_ids: nonempty list[str], reasons: list[str] |
| 2 investigate(detection) | prior InvestigationInput plus incident_id: str, evidence_ids: nonempty list[str], permission_ids: list[str], affected_asset_ids: nonempty list[str], severity: low/medium/high/critical |
| 3 analyze(investigation) | IntelligenceOutput already documented above |
| 5 match_and_draft(report) | incident_id: str, employee_matches: list of {recipient_id: str, asset_id: str, draft: str} |

Agent 2 extra raw context is available only as untrusted Agent 3 input. It is not
copied to persisted state/reports/P3 input. The final report's provisional fields
are incident_id, status, severity, evidence_ids, affected_asset_ids, detection,
investigation, intelligence. Employee matches remain a separate IncidentState
field. Severity always comes from validated P1 investigation; recipients always
come from validated P3, and must reference affected assets.

`IncidentState` has exactly the architecture §2.3 fields. Lifecycle status is
stored in the incidents row and final_report, **not added to IncidentState**.
Approval remains pending and notification remains not_sent. The orchestrator
never approves or sends notifications.

Bind actual functions with:

```python
from backend.workflow.orchestrator import WorkflowServices, workflow_services, run_incident_workflow
from backend.workflow.storage import SQLiteWorkflowStore

# Supply the real P1/P3 callables and a real sqlite3.Connection after reconciling
# the schema and contracts. No fake/default detector or employee matcher exists.
services = WorkflowServices(detect, investigate, event_exists, permission_exists,
                            match_and_draft, SQLiteWorkflowStore(connection))
with workflow_services(services):
    states = run_incident_workflow()
```

The store checks existing columns and creates no production tables. Expected
provisional columns are:

- incidents: incident_id (primary key), evidence_key (unique), status, state_json,
  final_report_json.
- audit_events: incident_id, actor_type, actor_id, action, resource_type,
  resource_id, details_json, timestamp.

**These are not a discovered P1 database schema.** The matching SQL exists only in
`backend/tests/fakes/schema.sql`. Adapt the P2 storage/audit adapters to P1's
actual schema before integration. The unique evidence key is JSON of sorted
unique detection evidence IDs; repeated evidence reuses the persisted state,
even if another detection supplies a new label. An incident ID cannot overwrite
a different evidence set. Incomplete incidents are reused without implicit retry.

Audit details are allowlisted summaries of IDs/statuses, never raw logs or
employee records. The writer redacts configured keys, common credential patterns,
and email addresses. Error details include step and exception type, not raw
exception strings. If detection fails before producing incidents, it records a
workflow error and raises without inventing an incident. If SQLite/audit itself
is unavailable, returned errors record that persistence failed; no audit success
is claimed.

Separate folders exist at `backend/agents/agent1/` through `agent5/`, each with
an empty initializer and a README pointing to the canonical required path.
Implementations were not moved, duplicated, or substituted into P1/P3 namespaces.

The runnable fixture demo lives at `backend/tests/run_fixture_workflow.py` and
imports only explicitly test-only fake P1/P3 modules. It uses a temporary SQLite
database, the real RAG/Agent 3, and an explicitly empty Nemotron key. It runs twice,
asserts idempotency, prints the state/audit, and deletes its temporary SQLite DB.
