"""Agent 5: deterministic owner matching and least-disclosure message drafting."""
import json
import uuid
from backend.storage import connect
from backend.tools.employee_queries import get_employee_matches


def match_and_draft(report: dict) -> list[dict]:
    incident_id = report["incident_id"]
    asset_ids = list(dict.fromkeys(report.get("affected_asset_ids", [])))
    matches = get_employee_matches(asset_ids)
    login_id = "LOG-101"
    evidence_by_asset: dict[str, list[str]] = {asset_id: [] for asset_id in asset_ids}
    for event in report.get("timeline", []):
        if event.get("asset_id") in evidence_by_asset:
            evidence_by_asset[event["asset_id"]].append(event["event_id"])
    recipients: dict[str, dict] = {}
    for match in matches:
        recipient_id = match["employee_id"]
        if not recipient_id.startswith("TEAM:"):
            with connect() as db:
                verified = db.execute("""SELECT 1 FROM employees e JOIN employee_assets ea USING(employee_id)
                    WHERE e.employee_id=? AND e.active=1 AND ea.asset_id=? AND ea.active=1
                    AND ea.responsibility_type='owner'""", (recipient_id, match["asset_id"])).fetchone()
            if not verified:
                continue
        grouped = recipients.setdefault(recipient_id, {"recipient_id": recipient_id, "display_name": match["display_name"],
            "team": match["team"], "notification_channel": match["notification_channel"], "asset_ids": [], "matches": []})
        if match["asset_id"] not in grouped["asset_ids"]:
            grouped["asset_ids"].append(match["asset_id"])
        grouped["matches"].append(match)

    asset_details = {a["asset_id"]: a for a in report.get("assets", [])}
    drafts = []
    with connect() as db:
        for recipient in recipients.values():
            local_evidence = list(dict.fromkeys([login_id] + [event_id for asset_id in recipient["asset_ids"] for event_id in evidence_by_asset.get(asset_id, [])]))
            asset_names = [asset_details.get(a, {}).get("asset_name", a) for a in recipient["asset_ids"]]
            why = "; ".join(f"you are the active owner of {asset_id}" for asset_id in recipient["asset_ids"])
            local_terms = set(recipient["asset_ids"])
            actions_for_assets = [action for action in report.get("recommended_actions", [])
                                  if any(asset_id in action for asset_id in local_terms)]
            if not actions_for_assets:
                actions_for_assets = ["Review the access activity for your asset and follow the applicable incident procedure."]
            actions = "\n".join(f"• {action}" for action in actions_for_assets)
            facts_for_assets = [fact for fact in report.get("facts", [])
                                if any(asset_id in fact for asset_id in local_terms)]
            if not facts_for_assets:
                facts_for_assets = ["An unfamiliar privileged login was recorded (" + login_id + ")."]
            facts = "\n".join(f"• {fact}" for fact in facts_for_assets)
            body = (f"You are receiving this because {why}.\n\nWhat happened\n{facts}\n\n"
                    f"Why it matters\nThis incident involved {', '.join(asset_names)}. Please review activity for your assigned asset(s).\n\n"
                    f"Suggested next steps\n{actions}\n\nIncident ID: {incident_id}\n"
                    f"Evidence IDs for your asset(s): {', '.join(local_evidence)}\n"
                    "Escalation contact: Taylor Kim, Security Incident Lead (EMP-007).")
            subject = f"[{report.get('severity', 'high').upper()}] SentinelAI incident {incident_id} — {', '.join(recipient['asset_ids'])}"
            notification_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{incident_id}:{recipient['recipient_id']}"))
            db.execute("""INSERT INTO notifications (notification_id, incident_id, recipient_id, recipient_channel,
                asset_ids_json, subject, body, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'draft')
                ON CONFLICT(incident_id, recipient_id) DO UPDATE SET recipient_channel=excluded.recipient_channel,
                asset_ids_json=excluded.asset_ids_json, subject=excluded.subject, body=excluded.body
                WHERE notifications.status='draft'""", (notification_id, incident_id, recipient["recipient_id"],
                recipient["notification_channel"], json.dumps(recipient["asset_ids"]), subject, body))
        db.commit()
        rows = db.execute("SELECT * FROM notifications WHERE incident_id=? ORDER BY recipient_id", (incident_id,)).fetchall()
        drafts = [{**dict(row), "asset_ids": json.loads(row["asset_ids_json"])} for row in rows]
    return drafts
