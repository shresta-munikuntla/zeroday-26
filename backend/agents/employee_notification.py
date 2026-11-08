"""Agent 5: owner matching and least-disclosure message drafting."""
from __future__ import annotations

import json
import re
import uuid

from backend.storage import connect
from backend.tools.asset_queries import get_assets
from backend.tools.employee_queries import get_employee_matches, get_escalation_contact
from backend.tools.security_queries import get_security_events

_FACT_EVIDENCE_RE = re.compile(r"\b(?:LOG|PERM)-\d+(?:\.\d+)?\b")


def _agent_outputs(report: dict, investigation: dict | None = None) -> tuple[dict, dict, dict]:
    """Accept P1/P2 contracts, a combined state, or the earlier flat report shape."""
    if investigation is not None:
        return report, investigation, {}
    detection = report.get("detection") or report.get("agent1") or report
    investigated = report.get("investigation") or report.get("agent2") or report
    intelligence = report.get("intelligence") or {}
    return detection, investigated, intelligence


def _login_event_ids(detection: dict, investigation: dict, all_evidence: set[str]) -> list[str]:
    explicit = detection.get("login_event_ids") or investigation.get("login_event_ids")
    if explicit is not None:
        return [event_id for event_id in explicit if event_id in all_evidence]

    # The old flat fixture carries structured timeline event types. Keep accepting it,
    # but never assume a particular LOG identifier.
    for event in investigation.get("timeline", []):
        if event.get("event_type") == "login" and event.get("event_id") in all_evidence:
            return [event["event_id"]]

    # Agent 1 provides the account, time window, and evidence set. Use those values to
    # identify login evidence through the read-only P1 tool layer.
    event_ids = []
    time_window = detection.get("time_window") or {}
    for account_id in detection.get("account_ids", []):
        filters = {"account_id": account_id, "event_type": "login"}
        if time_window.get("start"):
            filters["start"] = time_window["start"]
        if time_window.get("end"):
            filters["end"] = time_window["end"]
        for event in get_security_events(filters):
            if event["event_id"] in all_evidence:
                event_ids.append(event["event_id"])
    return list(dict.fromkeys(event_ids))


def _asset_evidence(investigation: dict, asset_ids: list[str], all_evidence: set[str]) -> dict[str, list[str]]:
    """Map Agent 2's per-asset access and permission evidence to its asset."""
    result = {asset_id: [] for asset_id in asset_ids}
    for asset in investigation.get("affected_assets", []):
        asset_id = asset.get("asset_id")
        if asset_id not in result:
            continue
        evidence = list(asset.get("evidence_ids", []))
        evidence.extend(asset.get("successful_access_ids", []))
        evidence.extend(asset.get("denied_access_ids", []))
        if asset.get("permission_id"):
            evidence.append(asset["permission_id"])
        result[asset_id].extend(x for x in evidence if x in all_evidence)

    # Compatibility for callers that already pass a flat report with structured events.
    for event in investigation.get("timeline", []):
        asset_id = event.get("asset_id")
        if asset_id in result:
            ids = event.get("evidence_ids") or [event.get("event_id")]
            result[asset_id].extend(x for x in ids if x and x in all_evidence)
    return {asset_id: list(dict.fromkeys(ids)) for asset_id, ids in result.items()}


def _asset_facts(facts: list[str], local_assets: list[str], other_assets: list[str],
                 local_names: list[str], other_names: list[str],
                 local_evidence: set[str], login_ids: set[str]) -> list[str]:
    selected = []
    for fact in facts:
        if any(value and value in fact for value in [*other_assets, *other_names]):
            continue
        cited = set(_FACT_EVIDENCE_RE.findall(fact))
        if cited and cited.issubset(local_evidence):
            selected.append(fact)
        elif not cited and any(value and value in fact for value in [*local_assets, *local_names]):
            selected.append(fact)
        elif cited and cited.issubset(login_ids):
            # Shared authentication facts apply to every affected asset owner.
            selected.append(fact)
    return list(dict.fromkeys(selected))


def _action_text(action: str | dict) -> str:
    if isinstance(action, str):
        return action
    if isinstance(action, dict):
        return str(action.get("action") or action.get("recommendation") or action.get("text") or "")
    return ""


def match_and_draft(report: dict, investigation: dict | None = None) -> list[dict]:
    """Create one owner-specific draft from Agent 1/2 output (optionally Agent 3 guidance).

    `report` may contain nested `detection`, `investigation`, and `intelligence` outputs,
    or the two P1/P2 outputs may be passed as separate arguments. A flat legacy report is
    still accepted for compatibility, but event IDs are always derived from its contents.
    """
    detection, investigation, intelligence = _agent_outputs(report, investigation)
    incident_id = detection.get("incident_id") or investigation.get("incident_id") or report.get("incident_id")
    if not incident_id:
        raise ValueError("Agent 1/2 output must include an incident_id")
    asset_ids = list(dict.fromkeys(detection.get("affected_asset_ids") or report.get("affected_asset_ids", [])))
    if not asset_ids:
        return []

    evidence = set(detection.get("evidence_ids", [])) | set(investigation.get("evidence_ids", []))
    if not evidence:
        evidence = set(report.get("evidence_ids", []))
    login_ids = _login_event_ids(detection, investigation, evidence)
    evidence_by_asset = _asset_evidence(investigation, asset_ids, evidence)
    matches = get_employee_matches(asset_ids)

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
        grouped = recipients.setdefault(recipient_id, {"recipient_id": recipient_id,
            "display_name": match["display_name"], "team": match["team"],
            "notification_channel": match["notification_channel"], "asset_ids": []})
        if match["asset_id"] not in grouped["asset_ids"]:
            grouped["asset_ids"].append(match["asset_id"])

    asset_records = get_assets(asset_ids)
    supplied_assets = {a["asset_id"]: a for a in
                       (investigation.get("affected_assets") or report.get("assets", [])) if a.get("asset_id")}
    severity = (investigation.get("severity") or detection.get("severity_initial")
                or report.get("severity") or "unknown")
    confirmed_facts = investigation.get("confirmed_facts") or report.get("facts", [])
    recommended_actions = (intelligence.get("recommended_actions") or report.get("recommended_actions")
                           or investigation.get("benign_explanations_to_check") or [])
    all_names = {a.get("asset_name") for a in asset_records.values() if a.get("asset_name")}
    drafts = []

    with connect() as db:
        for recipient in recipients.values():
            own_assets = recipient["asset_ids"]
            local_ids = list(dict.fromkeys(login_ids + [event_id for asset_id in own_assets
                                                         for event_id in evidence_by_asset.get(asset_id, [])]))
            local_evidence = set(local_ids)
            own_names = []
            for asset_id in own_assets:
                asset = supplied_assets.get(asset_id) or asset_records.get(asset_id, {})
                own_names.append(asset.get("asset_name") or asset_id)
            other_asset_ids = [asset_id for asset_id in asset_ids if asset_id not in own_assets]
            other_names = [asset_records.get(asset_id, {}).get("asset_name")
                           for asset_id in other_asset_ids]
            facts = _asset_facts(confirmed_facts, own_assets, other_asset_ids, own_names,
                                 other_names, local_evidence, set(login_ids))
            if not facts:
                facts = ["Review the observed activity associated with your assigned asset."]

            actions = []
            for item in recommended_actions:
                action = _action_text(item).strip()
                if not action or any(other_id in action for other_id in other_asset_ids):
                    continue
                if any(name and name in action for name in all_names if name not in own_names):
                    continue
                actions.append(action)
            if not actions:
                actions = ["Review the access activity for your assigned asset and follow the applicable incident procedure."]

            escalation = get_escalation_contact(recipient["team"])
            if escalation:
                escalation_text = f"{escalation['display_name']}, {escalation['role']} ({escalation['employee_id']})"
            else:
                escalation_text = "the Security Incident Lead"
            why = "; ".join(f"you are the active owner of {asset_id}" for asset_id in own_assets)
            body = (f"You are receiving this because {why}.\n\nWhat happened\n"
                    + "\n".join(f"• {fact}" for fact in facts)
                    + f"\n\nWhy it matters\nPlease review the incident activity for {', '.join(own_names)}.\n\n"
                    + "Suggested next steps\n" + "\n".join(f"• {action}" for action in actions)
                    + f"\n\nIncident ID: {incident_id}\nEvidence IDs for your asset(s): "
                    + (", ".join(local_ids) if local_ids else "No event evidence was attached by the investigation.")
                    + f"\nEscalation contact: {escalation_text}.")
            subject = f"[{str(severity).upper()}] SentinelAI incident {incident_id} — {', '.join(own_assets)}"
            notification_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{incident_id}:{recipient['recipient_id']}"))
            db.execute("""INSERT INTO notifications (notification_id, incident_id, recipient_id, recipient_channel,
                asset_ids_json, subject, body, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'draft')
                ON CONFLICT(incident_id, recipient_id) DO UPDATE SET recipient_channel=excluded.recipient_channel,
                asset_ids_json=excluded.asset_ids_json, subject=excluded.subject, body=excluded.body
                WHERE notifications.status='draft'""", (notification_id, incident_id, recipient["recipient_id"],
                recipient["notification_channel"], json.dumps(own_assets), subject, body))
        db.commit()
        rows = db.execute("SELECT * FROM notifications WHERE incident_id=? ORDER BY recipient_id", (incident_id,)).fetchall()
        drafts = [{**dict(row), "asset_ids": json.loads(row["asset_ids_json"])} for row in rows]
    return drafts
