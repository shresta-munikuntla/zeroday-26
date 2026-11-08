"""Read-only query functions for security logs, accounts, permissions, networks, windows.

Agents never write SQL; they call these. Every function validates input, uses '?' placeholders,
and returns plain dicts (JSON columns already decoded).
"""
import ipaddress
from datetime import datetime

from backend.database.db import check_id, connection, normalize_ts, parse_ts, row_to_dict

ALLOWED_EVENT_FILTERS = {"account_id", "event_type", "asset_id", "status", "start", "end"}
_EVENT_COLUMNS = "event_id, timestamp, event_type, account_id, source_ip, asset_id, status, details_json"
_EQUALITY_FILTERS = ("account_id", "event_type", "asset_id", "status")
MAX_EVENTS = 5000


# ---------------------------------------------------------------- events
def get_security_events(filters: dict | None = None, limit: int = MAX_EVENTS) -> list[dict]:
    """Events matching `filters`, oldest first. Allowed keys: account_id, event_type, asset_id,
    status, start, end (inclusive ISO timestamps). Unknown keys raise ValueError."""
    filters = dict(filters or {})
    unknown = set(filters) - ALLOWED_EVENT_FILTERS
    if unknown:
        raise ValueError(f"unknown filter keys: {sorted(unknown)}")
    clauses, params = [], []
    for key in _EQUALITY_FILTERS:
        if key in filters:
            clauses.append(f"{key} = ?")                      # key comes from the constant tuple above
            params.append(check_id(filters[key], key))
    if "start" in filters:
        clauses.append("timestamp >= ?")
        params.append(normalize_ts(filters["start"]))
    if "end" in filters:
        clauses.append("timestamp <= ?")
        params.append(normalize_ts(filters["end"]))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(max(1, min(int(limit), MAX_EVENTS)))
    with connection() as conn:
        rows = conn.execute(
            f"SELECT {_EVENT_COLUMNS} FROM security_logs {where} ORDER BY timestamp, event_id LIMIT ?",
            params).fetchall()
    return [row_to_dict(r) for r in rows]


def get_account_activity(account_id: str, start: str, end: str) -> list[dict]:
    return get_security_events({"account_id": account_id, "start": start, "end": end})


def get_server_access_history(asset_id: str, start: str, end: str) -> list[dict]:
    return get_security_events({"asset_id": asset_id, "event_type": "server_access", "start": start, "end": end})


def get_related_events(account_id: str, asset_ids: list[str], start: str, end: str) -> list[dict]:
    """The account's events in the window that touch `asset_ids`, plus its authentication events
    (logins / failed logins have no asset)."""
    check_id(account_id, "account_id")
    assets = [check_id(a, "asset_id") for a in asset_ids]
    asset_clause = f"asset_id IN ({', '.join('?' for _ in assets)})" if assets else "0"
    with connection() as conn:
        rows = conn.execute(
            f"SELECT {_EVENT_COLUMNS} FROM security_logs "
            f"WHERE account_id = ? AND timestamp >= ? AND timestamp <= ? "
            f"AND ({asset_clause} OR asset_id IS NULL) ORDER BY timestamp, event_id",
            [account_id, normalize_ts(start), normalize_ts(end), *assets]).fetchall()
    return [row_to_dict(r) for r in rows]


def event_exists(event_id: str) -> bool:
    try:
        check_id(event_id, "event_id")
    except ValueError:
        return False
    with connection() as conn:
        return conn.execute("SELECT 1 FROM security_logs WHERE event_id = ?", (event_id,)).fetchone() is not None


# ---------------------------------------------------------------- accounts + permissions
def get_account(account_id: str) -> dict | None:
    """Limited account metadata: type, role, known IPs, status."""
    check_id(account_id, "account_id")
    with connection() as conn:
        row = conn.execute("SELECT account_id, account_type, role, known_ips_json, status "
                           "FROM accounts WHERE account_id = ?", (account_id,)).fetchone()
    return row_to_dict(row) if row else None


def get_account_permissions(account_id: str) -> list[dict]:
    check_id(account_id, "account_id")
    with connection() as conn:
        rows = conn.execute("SELECT permission_id, account_id, asset_id, permission_level, valid_from, valid_until "
                            "FROM permissions WHERE account_id = ? ORDER BY permission_id", (account_id,)).fetchall()
    return [dict(r) for r in rows]


def permission_exists(permission_id: str) -> bool:
    try:
        check_id(permission_id, "permission_id")
    except ValueError:
        return False
    with connection() as conn:
        return conn.execute("SELECT 1 FROM permissions WHERE permission_id = ?",
                            (permission_id,)).fetchone() is not None


def check_access(permissions: list[dict], asset_id: str, timestamp: str) -> dict:
    """Was access to `asset_id` allowed AT `timestamp`?  (decision: check at access time)

    Returns {"state": "authorized" | "expired" | "none", "permission_id": str | None, "valid_until": str | None}
      authorized: valid_from <= t < valid_until (empty valid_until = no end)
      expired:    a permission existed but ended before t (or hadn't started yet)
      none:       no permission row for this asset at all
    """
    t = parse_ts(timestamp)
    rows = [p for p in permissions if p["asset_id"] == asset_id]
    for p in rows:
        if parse_ts(p["valid_from"]) <= t and (p["valid_until"] is None or t < parse_ts(p["valid_until"])):
            return {"state": "authorized", "permission_id": p["permission_id"], "valid_until": p["valid_until"]}
    if rows:
        latest = max(rows, key=lambda p: p["valid_until"] or "")
        return {"state": "expired", "permission_id": latest["permission_id"], "valid_until": latest["valid_until"]}
    return {"state": "none", "permission_id": None, "valid_until": None}


# ---------------------------------------------------------------- benign-explanation checks
def get_approved_network(ip: str) -> str | None:
    """network_id of the approved network containing `ip`, else None (invalid IPs -> None)."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    with connection() as conn:
        rows = conn.execute("SELECT network_id, cidr FROM approved_networks ORDER BY network_id").fetchall()
    for r in rows:
        if addr in ipaddress.ip_network(r["cidr"], strict=False):
            return r["network_id"]
    return None


def is_approved_ip(ip: str) -> bool:
    return get_approved_network(ip) is not None


def get_maintenance_window(account_id: str, asset_id: str | None, timestamp: str) -> str | None:
    """window_id covering this account (and asset, if any) at this time of day, else None."""
    check_id(account_id, "account_id")
    hhmm = parse_ts(timestamp).strftime("%H:%M")
    with connection() as conn:
        rows = [row_to_dict(r) for r in conn.execute("SELECT * FROM maintenance_windows ORDER BY window_id")]
    for w in rows:
        if account_id not in w["account_ids_json"]:
            continue
        if asset_id is not None and asset_id not in w["asset_ids_json"]:
            continue
        if w["start_time_utc"] <= hhmm < w["end_time_utc"]:     # daily recurrence only
            return w["window_id"]
    return None


def in_maintenance_window(account_id: str, asset_id: str | None, timestamp: str) -> bool:
    return get_maintenance_window(account_id, asset_id, timestamp) is not None


def is_off_hours(dt: datetime, start_hour: int, end_hour: int) -> bool:
    """Outside Mon-Fri start_hour..end_hour UTC."""
    return dt.weekday() >= 5 or not (start_hour <= dt.hour < end_hour)
