from backend.database.db import connection, row_to_dict


def test_row_counts(seeded_db):
    assert seeded_db == {
        "assets": 8, "accounts": 5, "security_logs": 157, "permissions": 20, "teams": 5,
        "employees": 8, "employee_assets": 9, "approved_networks": 2, "maintenance_windows": 1,
    }


def test_foreign_keys_and_json_round_trip():
    with connection() as conn:
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        acct = row_to_dict(conn.execute("SELECT * FROM accounts WHERE account_id = 'admin_04'").fetchone())
        link = conn.execute("SELECT active FROM employee_assets WHERE employee_id = 'EMP-008'").fetchone()
    assert acct["known_ips_json"] == ["10.20.1.14"]
    assert link["active"] == 0


def test_manifest_is_not_loaded():
    with connection() as conn:
        tables = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert not any("manifest" in t for t in tables)


def test_workflow_tables_exist_and_are_empty():
    with connection() as conn:
        for table in ("incidents", "notifications", "audit_events"):
            assert conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"] == 0
