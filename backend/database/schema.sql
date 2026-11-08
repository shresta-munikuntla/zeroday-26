-- SentinelAI database schema (SQLite).
-- Conventions: timestamps are ISO-8601 UTC text ('2026-11-07T09:10:00Z');
-- *_json columns hold json.dumps() text; booleans are 0/1.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------- reference data
CREATE TABLE assets (
    asset_id      TEXT PRIMARY KEY,
    asset_name    TEXT NOT NULL,
    asset_type    TEXT NOT NULL CHECK (asset_type IN ('server', 'database', 'network_segment')),
    criticality   TEXT NOT NULL CHECK (criticality IN ('low', 'medium', 'high', 'critical')),
    owner_team    TEXT NOT NULL,
    environment   TEXT NOT NULL,
    description   TEXT
);

CREATE TABLE accounts (
    account_id      TEXT PRIMARY KEY,
    account_type    TEXT NOT NULL CHECK (account_type IN ('admin', 'service', 'employee')),
    role            TEXT,
    known_ips_json  TEXT NOT NULL DEFAULT '[]',
    status          TEXT NOT NULL CHECK (status IN ('active', 'disabled', 'test'))
);

CREATE TABLE security_logs (
    event_id      TEXT PRIMARY KEY,
    timestamp     TEXT NOT NULL,
    event_type    TEXT NOT NULL CHECK (event_type IN
                    ('login', 'failed_login', 'server_access', 'permission_change', 'network_connection')),
    account_id    TEXT NOT NULL REFERENCES accounts(account_id),
    source_ip     TEXT NOT NULL,
    asset_id      TEXT REFERENCES assets(asset_id),
    status        TEXT NOT NULL CHECK (status IN ('success', 'failure', 'blocked')),
    details_json  TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX idx_logs_account_time ON security_logs (account_id, timestamp);
CREATE INDEX idx_logs_asset_time   ON security_logs (asset_id, timestamp);

CREATE TABLE permissions (
    permission_id     TEXT PRIMARY KEY,
    account_id        TEXT NOT NULL REFERENCES accounts(account_id),
    asset_id          TEXT NOT NULL REFERENCES assets(asset_id),
    permission_level  TEXT NOT NULL CHECK (permission_level IN ('read', 'write', 'admin')),
    valid_from        TEXT NOT NULL,
    valid_until       TEXT                -- NULL = no end date
);
CREATE INDEX idx_permissions_account ON permissions (account_id);

-- escalation_contact columns hold an employee_id but have no FK:
-- teams <-> employees would otherwise be a circular reference.
CREATE TABLE teams (
    team                TEXT PRIMARY KEY,
    team_channel        TEXT NOT NULL,
    escalation_contact  TEXT NOT NULL
);

CREATE TABLE employees (
    employee_id            TEXT PRIMARY KEY,
    display_name           TEXT NOT NULL,
    role                   TEXT NOT NULL,
    team                   TEXT NOT NULL REFERENCES teams(team),
    responsibilities_json  TEXT NOT NULL DEFAULT '[]',
    escalation_contact     TEXT NOT NULL,
    notification_channel   TEXT NOT NULL
);

CREATE TABLE employee_assets (
    employee_id          TEXT NOT NULL REFERENCES employees(employee_id),
    asset_id             TEXT NOT NULL REFERENCES assets(asset_id),
    responsibility_type  TEXT NOT NULL CHECK (responsibility_type IN ('owner', 'operator', 'backup')),
    active               INTEGER NOT NULL CHECK (active IN (0, 1)),
    PRIMARY KEY (employee_id, asset_id)
);

CREATE TABLE approved_networks (
    network_id    TEXT PRIMARY KEY,
    cidr          TEXT NOT NULL,
    description   TEXT,
    approved_for  TEXT
);

CREATE TABLE maintenance_windows (
    window_id         TEXT PRIMARY KEY,
    description       TEXT,
    recurrence        TEXT NOT NULL CHECK (recurrence IN ('daily')),
    start_time_utc    TEXT NOT NULL,      -- 'HH:MM'
    end_time_utc      TEXT NOT NULL,      -- 'HH:MM', exclusive
    account_ids_json  TEXT NOT NULL DEFAULT '[]',
    asset_ids_json    TEXT NOT NULL DEFAULT '[]'
);

-- ---------------------------------------------------------------- workflow records
CREATE TABLE incidents (
    incident_id          TEXT PRIMARY KEY,                 -- 'INC-001'
    created_at           TEXT NOT NULL,
    status               TEXT NOT NULL CHECK (status IN
                           ('detected', 'investigating', 'awaiting_approval', 'notified',
                            'closed', 'incomplete', 'rejected')),
    severity             TEXT CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    summary              TEXT,
    evidence_key         TEXT UNIQUE,                      -- sorted evidence IDs joined by ',' (duplicate guard)
    final_report_json    TEXT,
    approval_status      TEXT NOT NULL DEFAULT 'pending'  CHECK (approval_status IN ('pending', 'approved', 'rejected')),
    notification_status  TEXT NOT NULL DEFAULT 'not_sent' CHECK (notification_status IN ('not_sent', 'sent', 'failed', 'mocked'))
);

-- Columns agreed for P3 (issue #31). recipient_id is an employee_id or, for team fallback, a team name.
CREATE TABLE notifications (
    notification_id    TEXT PRIMARY KEY,
    incident_id        TEXT NOT NULL REFERENCES incidents(incident_id),
    recipient_id       TEXT NOT NULL,
    recipient_channel  TEXT NOT NULL,
    asset_ids_json     TEXT NOT NULL DEFAULT '[]',
    subject            TEXT NOT NULL,
    body               TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'draft' CHECK (status IN
                         ('draft', 'approved', 'sent', 'mocked', 'failed', 'rejected')),
    approved_by        TEXT,
    approved_at        TEXT,
    sent_at            TEXT,
    delivery_result    TEXT,
    UNIQUE (incident_id, recipient_id)                    -- one message per incident + recipient
);

CREATE TABLE audit_events (
    audit_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id    TEXT REFERENCES incidents(incident_id),
    actor_type     TEXT NOT NULL CHECK (actor_type IN ('user', 'agent', 'system')),
    actor_id       TEXT NOT NULL,
    action         TEXT NOT NULL,
    resource_type  TEXT,
    resource_id    TEXT,
    timestamp      TEXT NOT NULL,
    details_json   TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX idx_audit_incident ON audit_events (incident_id);
