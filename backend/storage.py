"""Small SQLite store initialized from the repository's synthetic fixtures."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("DATABASE_PATH", str(ROOT / "data" / "sentinelai.sqlite3")))


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def fixture(name: str) -> list[dict[str, Any]]:
    return json.loads((ROOT / "data" / "seed" / f"{name}.json").read_text())


def initialize() -> None:
    with connect() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS employees (
                employee_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, role TEXT NOT NULL,
                team TEXT NOT NULL, notification_channel TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS assets (
                asset_id TEXT PRIMARY KEY, asset_name TEXT NOT NULL, asset_type TEXT NOT NULL,
                criticality TEXT NOT NULL, owner_team TEXT NOT NULL, environment TEXT NOT NULL,
                description TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS employee_assets (
                employee_id TEXT NOT NULL, asset_id TEXT NOT NULL, responsibility_type TEXT NOT NULL,
                active INTEGER NOT NULL, PRIMARY KEY(employee_id, asset_id)
            );
            CREATE TABLE IF NOT EXISTS teams (
                team TEXT PRIMARY KEY, team_channel TEXT NOT NULL, escalation_contact TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS notifications (
                notification_id TEXT PRIMARY KEY, incident_id TEXT NOT NULL, recipient_id TEXT NOT NULL,
                recipient_channel TEXT NOT NULL, asset_ids_json TEXT NOT NULL, subject TEXT NOT NULL,
                body TEXT NOT NULL, status TEXT NOT NULL, approved_by TEXT, approved_at TEXT,
                sent_at TEXT, delivery_result TEXT, UNIQUE(incident_id, recipient_id)
            );
            CREATE TABLE IF NOT EXISTS incidents (
                incident_id TEXT PRIMARY KEY, severity TEXT NOT NULL, status TEXT NOT NULL,
                approval_status TEXT NOT NULL, summary TEXT NOT NULL, report_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT NOT NULL,
                actor_id TEXT NOT NULL, action TEXT NOT NULL, detail_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)
        if db.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 0:
            db.executemany("INSERT INTO employees VALUES (?, ?, ?, ?, ?, 1)", [
                (e["employee_id"], e["display_name"], e["role"], e["team"], e["notification_channel"])
                for e in fixture("employees")
            ])
            db.executemany("INSERT INTO assets VALUES (?, ?, ?, ?, ?, ?, ?)", [
                tuple(a[k] for k in ("asset_id", "asset_name", "asset_type", "criticality", "owner_team", "environment", "description"))
                for a in fixture("assets")
            ])
            db.executemany("INSERT INTO employee_assets VALUES (?, ?, ?, ?)", [
                (m["employee_id"], m["asset_id"], m["responsibility_type"], int(m["active"]))
                for m in fixture("employee_assets")
            ])
            db.executemany("INSERT INTO teams VALUES (?, ?, ?)", [
                (t["team"], t["team_channel"], t["escalation_contact"]) for t in fixture("teams")
            ])
def rows(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with connect() as db:
        return [dict(r) for r in db.execute(query, params).fetchall()]
