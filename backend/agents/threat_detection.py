"""Agent 1 - Threat Detection.

Deterministic rules decide; nothing here calls an LLM. Output follows the Agent 1 contract
(spec section 2) plus `rules_triggered`, which Agent 2 uses for its confidence score.

Usage:  python -m backend.agents.threat_detection [--out path.json]
"""
import argparse
import json
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

from backend.agents.severity import rate_severity
from backend.database.db import find_incident_by_evidence, format_ts, next_incident_number, parse_ts
from backend.tools.asset_queries import get_assets
from backend.tools.security_queries import (
    check_access, get_account, get_account_permissions, get_approved_network,
    get_maintenance_window, get_security_events, is_off_hours,
)

# Thresholds (match POL-001). Change here, nowhere else.
GROUP_WINDOW_MIN = 30          # max gap between events of one incident
FAILED_LOGIN_LIMIT = 5         # R3: failures ...
FAILED_LOGIN_WINDOW_MIN = 10   #     ... within this many minutes
BURST_ASSETS = 3               # R4: distinct assets ...
BURST_WINDOW_MIN = 15          #     ... within this many minutes, from an untrusted source
OFFICE_START_HOUR = 7          # off-hours = outside Mon-Fri 07:00-19:00 UTC (reason only, never a trigger)
OFFICE_END_HOUR = 19

R1, R2, R3, R4 = ("R1_unfamiliar_ip_login", "R2_access_without_valid_permission",
                  "R3_failed_login_burst", "R4_access_burst_untrusted_source")


def _trusted(event: dict, account: dict) -> bool:
    return event["source_ip"] in account["known_ips_json"] or get_approved_network(event["source_ip"]) is not None


def _rule_hits(events: list[dict], accounts: dict, permissions: dict) -> dict[str, set[str]]:
    """{event_id: {rule, ...}} for every event that trips a rule."""
    hits: dict[str, set[str]] = defaultdict(set)
    failures: dict[str, list[dict]] = defaultdict(list)
    untrusted_access: dict[tuple, list[dict]] = defaultdict(list)

    for e in events:
        account = accounts[e["account_id"]]
        if get_maintenance_window(e["account_id"], e["asset_id"], e["timestamp"]):
            continue                                                    # approved scheduled activity
        trusted = _trusted(e, account)
        if e["event_type"] == "login" and e["status"] == "success" and not trusted:
            hits[e["event_id"]].add(R1)
        if e["event_type"] == "server_access":
            if check_access(permissions[e["account_id"]], e["asset_id"], e["timestamp"])["state"] != "authorized":
                hits[e["event_id"]].add(R2)
            if not trusted:
                untrusted_access[(e["account_id"], e["source_ip"])].append(e)
        if e["event_type"] == "failed_login":
            failures[e["account_id"]].append(e)

    # R3: >= FAILED_LOGIN_LIMIT failures for one account inside a sliding window
    for fails in failures.values():
        for i, first in enumerate(fails):
            end = parse_ts(first["timestamp"]) + timedelta(minutes=FAILED_LOGIN_WINDOW_MIN)
            window = [f for f in fails[i:] if parse_ts(f["timestamp"]) < end]
            if len(window) >= FAILED_LOGIN_LIMIT:
                for f in window:
                    hits[f["event_id"]].add(R3)

    # R4: >= BURST_ASSETS distinct assets from the same untrusted source inside a sliding window
    for accesses in untrusted_access.values():
        for i, first in enumerate(accesses):
            end = parse_ts(first["timestamp"]) + timedelta(minutes=BURST_WINDOW_MIN)
            window = [a for a in accesses[i:] if parse_ts(a["timestamp"]) < end]
            if len({a["asset_id"] for a in window}) >= BURST_ASSETS:
                for a in window:
                    hits[a["event_id"]].add(R4)
    return hits


def _group(flagged: list[dict]) -> list[list[dict]]:
    """Same account + source IP, each event <= GROUP_WINDOW_MIN after the previous one."""
    by_source: dict[tuple, list[dict]] = defaultdict(list)
    for e in flagged:
        by_source[(e["account_id"], e["source_ip"])].append(e)
    groups = []
    for evs in by_source.values():
        evs.sort(key=lambda e: (e["timestamp"], e["event_id"]))
        current = [evs[0]]
        for e in evs[1:]:
            gap = parse_ts(e["timestamp"]) - parse_ts(current[-1]["timestamp"])
            if gap <= timedelta(minutes=GROUP_WINDOW_MIN):
                current.append(e)
            else:
                groups.append(current)
                current = [e]
        groups.append(current)
    return sorted(groups, key=lambda g: g[0]["timestamp"])


def _ids(events: list[dict]) -> str:
    return ", ".join(e["event_id"] for e in events)


def _build_detection(group: list[dict], hits: dict, account: dict, assets: dict, incident_id: str) -> dict:
    acct, ip = group[0]["account_id"], group[0]["source_ip"]
    rules = sorted({r for e in group for r in hits[e["event_id"]]})
    asset_ids = list(dict.fromkeys(e["asset_id"] for e in group if e["asset_id"]))   # first-touch order
    start, end = parse_ts(group[0]["timestamp"]), parse_ts(group[-1]["timestamp"])
    minutes = int((end - start).total_seconds() // 60)

    by_rule = {r: [e for e in group if r in hits[e["event_id"]]] for r in rules}
    reasons = []
    if R1 in by_rule:
        reasons.append(f"Successful login from {ip}, which is not in {acct}'s known-IP list "
                       f"and not inside any approved network ({_ids(by_rule[R1])})")
    if R2 in by_rule:
        reasons.append(f"Access to assets without a currently valid permission ({_ids(by_rule[R2])})")
    if R3 in by_rule:
        reasons.append(f"{len(by_rule[R3])} failed logins within {FAILED_LOGIN_WINDOW_MIN} minutes "
                       f"({_ids(by_rule[R3])})")
    if R4 in by_rule:
        n = len({e['asset_id'] for e in by_rule[R4]})
        reasons.append(f"Access to {n} different assets within {BURST_WINDOW_MIN} minutes "
                       f"from an untrusted source ({_ids(by_rule[R4])})")
    off = [e for e in group if is_off_hours(parse_ts(e["timestamp"]), OFFICE_START_HOUR, OFFICE_END_HOUR)]
    if off:
        reasons.append(f"Activity outside Mon-Fri {OFFICE_START_HOUR:02d}:00-{OFFICE_END_HOUR:02d}:00 UTC "
                       f"({start.strftime('%A')}) ({_ids(off)})")

    did = []
    if any(e["event_type"] == "login" for e in group):
        did.append(f"logged in from unfamiliar IP {ip}")
    if asset_ids:
        did.append(f"accessed or attempted {len(asset_ids)} asset(s) within {minutes} minutes")
    if R3 in by_rule:
        did.append(f"had {len(by_rule[R3])} failed logins")
    summary = f"{account['account_type'].capitalize()} account {acct} " + " and ".join(did) + "."

    uncertainties = ["The source IP may belong to an authorized but unregistered VPN or remote-access path.",
                     "Access alone is not proof of compromise; the account holder has not been contacted."]
    if off:
        uncertainties.append("Off-hours activity may be unrecorded emergency maintenance.")

    return {
        "incident_id": incident_id,
        "detection_status": "suspicious",
        "summary": summary,
        "severity_initial": rate_severity(account["account_type"],
                                          [assets[a]["criticality"] for a in asset_ids if a in assets],
                                          unauthorized_access=R2 in by_rule),
        "account_ids": [acct],
        "source_ip_addresses": [ip],
        "affected_asset_ids": asset_ids,
        "time_window": {"start": format_ts(start), "end": format_ts(end)},
        "evidence_ids": [e["event_id"] for e in group],
        "reasons": reasons,
        "uncertainties": uncertainties,
        "rules_triggered": rules,
    }


def detect(filters: dict | None = None) -> list[dict]:
    """Run all rules over the logs (optionally filtered) and return one detection per candidate incident.
    Re-running on the same evidence returns the same incident_id if the orchestrator already saved it."""
    events = get_security_events(filters)
    accounts = {a: get_account(a) for a in {e["account_id"] for e in events}}
    permissions = {a: get_account_permissions(a) for a in accounts}
    hits = _rule_hits(events, accounts, permissions)
    flagged = [e for e in events if e["event_id"] in hits]
    groups = _group(flagged)
    assets = get_assets(list({e["asset_id"] for e in flagged if e["asset_id"]}))

    detections, next_number = [], next_incident_number()
    for g in groups:
        incident_id = find_incident_by_evidence([e["event_id"] for e in g])
        if incident_id is None:
            incident_id, next_number = f"INC-{next_number:03d}", next_number + 1
        detections.append(_build_detection(g, hits, accounts[g[0]["account_id"]], assets, incident_id))
    return detections


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Agent 1 on the seeded database.")
    parser.add_argument("--out", help="write JSON to this file (UTF-8) instead of printing")
    args = parser.parse_args()
    text = json.dumps(detect(), indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
