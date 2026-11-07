"""Append-only audit events used by approval and delivery routes."""
import json
from backend.storage import connect


def write_audit_event(incident_id: str, actor_id: str, action: str, detail: dict) -> None:
    with connect() as db:
        db.execute("INSERT INTO audit_events (incident_id, actor_id, action, detail_json) VALUES (?, ?, ?, ?)",
                   (incident_id, actor_id, action, json.dumps(detail)))


def list_audit_events(incident_id: str) -> list[dict]:
    with connect() as db:
        events = db.execute("SELECT * FROM audit_events WHERE incident_id = ? ORDER BY event_id", (incident_id,)).fetchall()
    return [{**dict(event), "detail": json.loads(event["detail_json"])} for event in events]
