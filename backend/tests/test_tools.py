import pytest

from backend.tools.asset_queries import get_assets, get_server_details
from backend.tools.security_queries import (
    check_access, event_exists, get_account_permissions, get_approved_network, get_related_events,
    get_security_events, in_maintenance_window, permission_exists,
)


def test_unknown_filter_rejected():
    with pytest.raises(ValueError):
        get_security_events({"account_id": "admin_04", "password": "x"})


def test_injection_shaped_input_rejected():
    with pytest.raises(ValueError):
        get_security_events({"account_id": "admin_04' OR '1'='1"})
    with pytest.raises(ValueError):
        get_security_events({"start": "yesterday"})


def test_filters_and_ordering():
    events = get_security_events({"account_id": "admin_04", "start": "2026-11-07T00:00:00Z"})
    assert [e["event_id"] for e in events] == ["LOG-101", "LOG-102", "LOG-103", "LOG-104", "LOG-105"]
    assert isinstance(events[0]["details_json"], dict)


def test_related_events_include_logins():
    ids = [e["event_id"] for e in get_related_events(
        "admin_04", ["DC-DB-01"], "2026-11-07T09:00:00Z", "2026-11-07T09:30:00Z")]
    assert ids == ["LOG-101", "LOG-104", "LOG-105"]


def test_check_access_states():
    perms = get_account_permissions("admin_04")
    t = "2026-11-07T09:14:00Z"
    assert check_access(perms, "DC-SRV-04", t)["state"] == "authorized"
    assert check_access(perms, "DC-SRV-05", t) == {"state": "expired", "permission_id": "PERM-003",
                                                    "valid_until": "2026-10-01T00:00:00Z"}
    assert check_access(perms, "DC-DB-01", t)["state"] == "none"
    assert check_access(perms, "DC-SRV-05", "2026-09-15T00:00:00Z")["state"] == "authorized"


def test_benign_checks():
    assert get_approved_network("203.0.113.50") == "NET-001"
    assert get_approved_network("198.51.100.24") is None
    assert get_approved_network("not-an-ip") is None
    assert in_maintenance_window("svc_backup", "DC-DB-01", "2026-11-07T02:19:00Z")
    assert not in_maintenance_window("svc_backup", "DC-DB-01", "2026-11-07T03:00:00Z")
    assert not in_maintenance_window("admin_04", "DC-SRV-04", "2026-11-07T02:30:00Z")


def test_existence_checks():
    assert event_exists("LOG-101") and not event_exists("LOG-999") and not event_exists("x' OR 1=1")
    assert permission_exists("PERM-003") and not permission_exists("PERM-999")


def test_assets():
    assert get_server_details("DC-DB-01")["criticality"] == "critical"
    assert get_server_details("DC-NOPE") is None
    assert set(get_assets(["DC-SRV-04", "DC-NOPE"])) == {"DC-SRV-04"}
