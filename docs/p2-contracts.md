# P2 contracts and teammate integration

`run_incident_workflow()` binds real P1 and P3 functions automatically through
`backend/workflow/integration.py`. API startup and run-demo use the same path.
Explicit `workflow_services(WorkflowServices(...))` remains for tests/adapters;
production never imports fixture agents or reads the scenario manifest.

## Contract sources

Architecture §2.3 defines `IncidentState` exactly: incident_id, detection,
investigation, intelligence, employee_matches, final_report, approval_status,
notification_status, and errors. Lifecycle status is persisted in the incident
row and final report rather than adding an undocumented state field.

The architecture specifies Agent 3's six output groups, but references an external
spec for detailed nested contracts. That spec is absent. The existing nested P2
schema is retained; native P1/P3 models follow their actual implementations.

## Native validation before adaptation

`backend/workflow/validators.py` defines strict native models:

- `NativeAgent1Output`: ID, detection_status, summary, severity_initial, accounts,
  source IP addresses, assets, time_window, evidence IDs, reasons, uncertainties,
  and rules_triggered.
- `NativeAgent2Output`: ID, investigation_status, timeline, affected_assets,
  potential_impact, confirmed_facts, hypotheses, benign_explanations_to_check,
  checks_performed, severity, confidence, and evidence IDs. Nested timeline and
  per-asset evidence are validated against P1's existence functions.
- `NativeAgent5Draft`: P3's notification row plus decoded asset_ids. Extra
  database delivery/approval metadata is allowed; required draft fields are not
  defaulted. Each draft must belong to the report incident.

The explicit workflow adapter contracts (`Agent1Output`, `Agent2Output`,
`Agent5Output`) also support small, labelled test fixtures. Native runtime outputs
are validated before conversion to these compact fields. Missing native fields
are errors, not replaced by fixture values.

The investigation adapter derives `status` from `investigation_status`,
`permission_ids` from validated evidence, `affected_asset_ids` from affected_assets,
and search reasons from Agent 1's summary/reasons. It preserves the native
investigation fields for P3's owner-specific drafting. Standalone `analyze()` also
accepts raw native Agent 2 output, validates it, and uses checks_performed as
search context when no detection reasons were supplied.

## Agent 3 output

`backend/agents/intelligence_contract.py` contains these six required lists:

| Group | Required entry fields |
|---|---|
| matched_techniques | technique_id, name, relevance, source_document_ids |
| policy_references | policy_id, section, summary, source_document_ids |
| historical_cases | case_id, summary, relevance, source_document_ids |
| recommended_actions | action, source_document_ids |
| recommended_resources | title, url, source_document_ids |
| limitations | strings |

Extra model fields, including severity and recipients, are forbidden. Sources
are recorded in a request-local context during actual retrieval, independently
of the model's reported IDs. The orchestrator checks citations against that
receipt. Policy sections, technique/case identities, and resource URLs are checked
against retrieved metadata inside Agent 3. POL-099 is excluded from usable context
and recommendations even when included in the test index.

## Report, persistence, and audit

`FinalReport` validates the assembled report before P3 receives it. P1 severity
and P3 recipients remain deterministic. Successful state is saved as
awaiting_approval with pending approval and not_sent notification status. Errors
stop only the affected incident, retain validated intermediate results, and save
incomplete status. Whole-detector failure raises and is audited without a fake ID.

The existing P1 and P3 databases are currently separate. ApplicationWorkflowStore
adds only evidence_key/state_json/final_report_json columns and a unique evidence
index to P3's incidents table. It also persists incident records using P1's
existing schema and comma-joined evidence key, so P1's ID allocator sees them.
No P1 schema is replaced. Test-only SQLiteWorkflowStore uses an isolated explicit
schema. Two-store writes are not atomic; database consolidation is future work.

`write_audit_event` and `list_audit_events` support the bound P1-style audit schema
and the existing P3 audit schema. Calls without an explicit binding use P3's
application connection. Existing P3 API audit helper signatures are preserved.
Details are allowlisted, credential/email values redacted, and step outcomes
contain IDs/statuses rather than prompts, employee records, or provider errors.

See [p2-verification.md](p2-verification.md) for executed results, limitations,
mock/live environment examples, and the private SSH tunnel commands.
