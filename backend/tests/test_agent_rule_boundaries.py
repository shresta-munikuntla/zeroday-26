"""Controlled rule/grouping inputs for the correctness audit; no production changes."""
from copy import deepcopy
from backend.agents import threat_detection as a


def context(monkeypatch):
    monkeypatch.setattr(a, 'get_maintenance_window', lambda *args: None)
    monkeypatch.setattr(a, 'get_approved_network', lambda *args: None)
    return {'acct': {'known_ips_json': []}}, {'acct': []}


def event(i, minute, asset=None, kind='failed_login'):
    return {'event_id': f'LOG-TEST-{i}', 'account_id': 'acct', 'source_ip': '198.51.100.24',
            'timestamp': f'2026-11-07T09:{minute:02d}:00Z', 'event_type': kind,
            'asset_id': asset, 'status': 'failure' if kind == 'failed_login' else 'success'}


def test_r3_threshold_and_window(monkeypatch):
    accounts, permissions = context(monkeypatch)
    five = [event(i, t) for i, t in enumerate([0, 2, 4, 6, 9])]
    assert all(a.R3 in h for h in a._rule_hits(five, accounts, permissions).values())
    assert not a._rule_hits(five[:4], accounts, permissions)
    spread = [event(i, t) for i, t in enumerate([0, 11, 22, 33, 44])]
    assert not a._rule_hits(spread, accounts, permissions)


def test_r4_distinct_assets_and_window(monkeypatch):
    accounts, permissions = context(monkeypatch)
    events = [event(i, t, f'ASSET-{i}', 'server_access') for i, t in enumerate([0, 7, 14])]
    hits = a._rule_hits(events, accounts, permissions)
    assert all(a.R4 in hits[e['event_id']] for e in events)
    for e in events:
        e['asset_id'] = 'SAME-ASSET'
    assert not any(a.R4 in h for h in a._rule_hits(events, accounts, permissions).values())


def test_maintenance_excludes_all_rule_hits(monkeypatch):
    accounts, permissions = context(monkeypatch)
    monkeypatch.setattr(a, 'get_maintenance_window', lambda *args: 'MW-test')
    assert a._rule_hits([event(i, i) for i in range(5)], accounts, permissions) == {}


def test_grouping_account_source_and_gap():
    first = event(1, 0)
    near = event(2, 30)
    assert len(a._group([first, near])) == 1
    far = event(3, 31)
    assert len(a._group([first, far])) == 2
    other = deepcopy(near); other['source_ip'] = '203.0.113.8'
    assert len(a._group([first, other])) == 2
