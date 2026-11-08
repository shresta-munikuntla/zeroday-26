"""Agent 2 - Investigation and Impact Analysis.

Takes an Agent 1 detection, re-checks the evidence against the database, and returns the
Agent 2 contract (spec section 2). Deterministic; never claims compromise or data theft.

Usage:  python -m backend.agents.investigation [--out path.json]   (runs Agent 1 first)
"""
import argparse
import json
from datetime import timedelta
from pathlib import Path

from backend.agents.severity import rate_severity
from backend.agents.threat_detection import OFFICE_END_HOUR, OFFICE_START_HOUR, detect
from backend.database.db import format_ts, parse_ts
from backend.tools.asset_queries import get_assets
from backend.tools.security_queries import (
    check_access, get_account, get_account_activity, get_account_permissions,
    get_approved_network, get_maintenance_window, get_related_events, is_off_hours,
)

CONTEXT_MIN = 30          # look this far before/after the detection window
BASELINE_DAYS = 7         # history used for "is this unusual for the account?"
IMPACT_EVENT_TYPES = {"permission_change", "network_connection"}   # would indicate changes / transfer

# Confidence = 0.5 + 0.1 per Agent 1 rule fired + 0.1 if a critical asset is involved, capped at 0.9.
# An estimate for ranking, not a calibrated probability; never 1.0 without the account holder confirming.
CONFIDENCE_BASE, CONFIDENCE_PER_RULE, CONFIDENCE_CRITICAL, CONFIDENCE_MAX = 0.5, 0.1, 0.1, 0.9

_STATE_RANK = {"authorized": 0, "expired": 1, "none": 2}
REQUIRED_DETECTION_FIELDS = ("incident_id", "account_ids", "source_ip_addresses",
                             "affected_asset_ids", "time_window", "evidence_ids")


def _validate(detection: dict) -> None:
    missing = [f for f in REQUIRED_DETECTION_FIELDS if not detection.get(f)]
    if missing:
        raise ValueError(f"detection is missing {missing}")


def _describe(e: dict, access: dict | None, asset: dict | None, untrusted_ip: bool) -> str:
    who, ip = e["account_id"], e["source_ip"]
    if e["event_type"] == "login":
        text = f"{who} logged in from {ip}" if e["status"] == "success" else f"Login by {who} from {ip} {e['status']}"
        return text + (" (IP not in known-IP list or any approved network)." if untrusted_ip else ".")
    if e["event_type"] == "failed_login":
        return f"Failed login for {who} from {ip}."
    name = f"{e['asset_id']} ({asset['asset_name']})" if asset else str(e["asset_id"])
    verb = "accessed" if e["status"] == "success" else "attempted to access"
    result = "" if e["status"] == "success" else f" - {e['status']}"
    if access is None:
        return f"{who} {verb} {name}{result}."
    if access["state"] == "authorized":
        permission = f"permitted by {access['permission_id']}"
    elif access["state"] == "expired":
        permission = f"{access['permission_id']} expired {access['valid_until'][:10]}"
    else:
        permission = "no permission on record"
    return f"{who} {verb} {name}{result}; {permission}."


def investigate(detection: dict) -> dict:
    _validate(detection)
    incident_id = detection["incident_id"]
    account_id = detection["account_ids"][0]
    source_ips = set(detection["source_ip_addresses"])
    start = parse_ts(detection["time_window"]["start"]) - timedelta(minutes=CONTEXT_MIN)
    end = parse_ts(detection["time_window"]["end"]) + timedelta(minutes=CONTEXT_MIN)

    account = get_account(account_id)
    if account is None:
        raise ValueError(f"unknown account {account_id}")
    permissions = get_account_permissions(account_id)
    assets = get_assets(detection["affected_asset_ids"])
    events = get_related_events(account_id, detection["affected_asset_ids"], format_ts(start), format_ts(end))

    timeline, per_asset, evidence = [], {}, []
    for e in events:
        untrusted = e["source_ip"] not in account["known_ips_json"] and get_approved_network(e["source_ip"]) is None
        access = check_access(permissions, e["asset_id"], e["timestamp"]) if e["event_type"] == "server_access" else None
        ids = [e["event_id"]] + ([access["permission_id"]] if access and access["permission_id"] else [])
        timeline.append({"timestamp": e["timestamp"],
                         "description": _describe(e, access, assets.get(e["asset_id"]), untrusted),
                         "evidence_ids": ids})
        evidence += ids
        if access:
            a = per_asset.setdefault(e["asset_id"], {"state": "authorized", "permission_id": None,
                                                     "valid_until": None, "success": [], "failure": []})
            if _STATE_RANK[access["state"]] >= _STATE_RANK[a["state"]]:
                a.update(state=access["state"], permission_id=access["permission_id"], valid_until=access["valid_until"])
            a["success" if e["status"] == "success" else "failure"].append(e["event_id"])

    # ---- facts (provable from records) --------------------------------------------------
    facts = []
    for e in events:
        if e["event_type"] == "login" and e["status"] == "success" and e["source_ip"] in source_ips \
                and e["source_ip"] not in account["known_ips_json"] and get_approved_network(e["source_ip"]) is None:
            facts.append(f"{account_id} logged in from {e['source_ip']}, which is not in its known-IP list "
                         f"and not inside any approved network ({e['event_id']}).")
    for asset_id, a in per_asset.items():
        ok, bad = ", ".join(a["success"]), ", ".join(a["failure"])
        if a["state"] == "authorized":
            facts.append(f"{account_id} accessed {asset_id} under valid permission {a['permission_id']} ({ok}).")
        elif a["state"] == "expired" and a["success"]:
            facts.append(f"{account_id} accessed {asset_id} although {a['permission_id']} expired on "
                         f"{a['valid_until'][:10]} ({ok}).")
        if a["state"] == "none" and a["failure"]:
            facts.append(f"{account_id} made {len(a['failure'])} denied attempt(s) to access {asset_id}; "
                         f"no permission exists ({bad}).")
        if a["state"] == "none" and a["success"]:
            facts.append(f"{account_id} accessed {asset_id} with no permission on record ({ok}).")

    window_start = parse_ts(detection["time_window"]["start"])
    off_hours = is_off_hours(window_start, OFFICE_START_HOUR, OFFICE_END_HOUR)
    if off_hours:
        history = get_account_activity(account_id, format_ts(window_start - timedelta(days=BASELINE_DAYS)),
                                       format_ts(window_start - timedelta(seconds=1)))
        prior_off = [h for h in history if is_off_hours(parse_ts(h["timestamp"]), OFFICE_START_HOUR, OFFICE_END_HOUR)]
        if not prior_off:
            facts.append(f"Activity occurred on {window_start.strftime('%A')} outside Mon-Fri "
                         f"{OFFICE_START_HOUR:02d}:00-{OFFICE_END_HOUR:02d}:00 UTC; {account_id} has no off-hours "
                         f"activity in the previous {BASELINE_DAYS} days ({len(history)} events reviewed).")

    impact_events = [e for e in events if e["event_type"] in IMPACT_EVENT_TYPES]
    window_ids = [w for w in {get_maintenance_window(account_id, a, detection["time_window"]["start"])
                              for a in per_asset} if w]

    # ---- hypotheses + benign explanations (never stated as fact) ------------------------
    unauthorized_success = [k for k, a in per_asset.items() if a["state"] != "authorized" and a["success"]]
    denied_attempts = [k for k, a in per_asset.items() if a["state"] != "authorized" and a["failure"]]
    hypotheses, benign = [], []
    if unauthorized_success or denied_attempts:
        hypotheses.append(f"The {account_id} credentials may be in use by someone other than the account holder.")
    for k in unauthorized_success:
        if per_asset[k]["state"] == "expired":
            hypotheses.append(f"Credentials on {k} may not have been revoked when {per_asset[k]['permission_id']} expired.")
    critical_attempts = [k for k in denied_attempts if assets.get(k, {}).get("criticality") == "critical"]
    if critical_attempts:
        hypotheses.append(f"The denied attempts on {', '.join(critical_attempts)} may indicate an attempt "
                          f"to reach a critical asset.")
    if any(ip not in account["known_ips_json"] and get_approved_network(ip) is None for ip in source_ips):
        benign.append("The source IP may be a new or unregistered VPN / remote-access address (verify with Network Security).")
    if off_hours and not window_ids:
        benign.append(f"The activity may be unrecorded emergency maintenance (verify with the {account_id} account holder).")
    for k in unauthorized_success:
        if per_asset[k]["state"] == "expired":
            benign.append(f"Access to {k} may have been informally extended after {per_asset[k]['permission_id']} expired.")

    checks = [f"Source IP(s) {', '.join(sorted(source_ips))} checked against approved networks: "
              + ("match found." if any(get_approved_network(ip) for ip in source_ips) else "no match."),
              "Maintenance windows checked: " + (", ".join(window_ids) if window_ids else "none cover this activity."),
              f"Event types {sorted(IMPACT_EVENT_TYPES)} checked in the window: "
              + (", ".join(e["event_id"] for e in impact_events) if impact_events else "none found.")]

    # ---- impact, severity, confidence ----------------------------------------------------
    affected = [{"asset_id": k, "asset_name": assets[k]["asset_name"], "criticality": assets[k]["criticality"],
                 "owner_team": assets[k]["owner_team"], "authorization": a["state"],
                 "permission_id": a["permission_id"], "successful_access_ids": a["success"],
                 "denied_access_ids": a["failure"]}
                for k, a in per_asset.items() if k in assets]
    exposed = [f"{x['asset_id']} ({x['asset_name']}, {x['criticality']})" for x in affected
               if x["authorization"] != "authorized" and x["successful_access_ids"]]
    attempted = [f"{x['asset_id']} ({x['asset_name']}, {x['criticality']})" for x in affected
                 if x["authorization"] != "authorized" and not x["successful_access_ids"]]
    impact = []
    if exposed:
        impact.append(f"Access without a valid permission may expose services hosted on {', '.join(exposed)}.")
    if attempted:
        impact.append(f"Denied attempts targeted {', '.join(attempted)}; no successful access was recorded.")
    impact.append("No permission changes or data-transfer events were found in the logs."
                  if not impact_events else "Change or transfer events were found and need review.")

    unauthorized = bool(unauthorized_success or denied_attempts)
    severity = rate_severity(account["account_type"], [x["criticality"] for x in affected],
                             unauthorized_access=unauthorized, impact_confirmed=False)
    confidence = CONFIDENCE_BASE + CONFIDENCE_PER_RULE * len(detection.get("rules_triggered", []))
    if any(x["criticality"] == "critical" for x in affected):
        confidence += CONFIDENCE_CRITICAL
    confidence = round(min(confidence, CONFIDENCE_MAX), 2)

    if unauthorized_success:
        status = "potential_unauthorized_access"
    elif denied_attempts:
        status = "attempted_unauthorized_access"
    elif facts:
        status = "unverified_activity"
    else:
        status = "no_unauthorized_access_found"

    return {
        "incident_id": incident_id,
        "investigation_status": status,
        "timeline": timeline,
        "affected_assets": affected,
        "potential_impact": " ".join(impact),
        "confirmed_facts": facts,
        "hypotheses": hypotheses,
        "benign_explanations_to_check": benign,
        "checks_performed": checks,
        "severity": severity,
        "confidence": confidence,
        "evidence_ids": sorted(set(evidence)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Agent 1 then Agent 2 on the seeded database.")
    parser.add_argument("--out", help="write JSON to this file (UTF-8) instead of printing")
    args = parser.parse_args()
    text = json.dumps([investigate(d) for d in detect()], indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
