-- TEST-ONLY PROVISIONAL SCHEMA. Not a P1 migration or production schema.
CREATE TABLE incidents (
    incident_id TEXT PRIMARY KEY,
    evidence_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    state_json TEXT NOT NULL,
    final_report_json TEXT
);
CREATE TABLE audit_events (
    incident_id TEXT,
    actor_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    details_json TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
