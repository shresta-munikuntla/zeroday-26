"""End-to-end workflow injection tests with test-only P1/P3 integrations."""
from copy import deepcopy
import json
import os
from pathlib import Path
from unittest.mock import Mock

import pytest

from backend.agents import intelligence
from backend import config
from backend.tests.fakes import agent2, agent5
from backend.workflow.orchestrator import run_incident_workflow, workflow_services
from backend.security.audit import list_audit_events

ROOT = Path(__file__).resolve().parents[2]


def attack_investigation(detection):
    result = agent2.investigate(detection)
    log = next(x for x in json.loads((ROOT / 'data/seed/security_logs.json').read_text()) if x['event_id'] == 'LOG-190')
    result['log_context'] = log
    return result


def assert_protected(result, audit):
    state = result[0]
    encoded = json.dumps(result)
    assert state['errors'] == []
    assert state['final_report']['severity'] == 'high'
    assert state['final_report']['status'] == 'awaiting_approval'
    assert [(x['recipient_id'], x['asset_id']) for x in state['employee_matches']] == agent5.OWNERS
    assert '@' not in encoded
    assert 'POL-099' not in encoded
    assert '@' not in json.dumps(audit)
    assert all('POL-099' not in a['source_document_ids'] for a in state['intelligence']['recommended_actions'])


def test_log190_pol099_cannot_change_severity_or_recipients(services, monkeypatch):
    policy_text = (ROOT / 'data/knowledge/test_fixtures/POL-099-poisoned.md').read_text()
    source = {'doc_id': 'POL-003', 'title': 'Privilege', 'section': 'Expired',
              'source_type': 'internal_policy_sample', 'text': 'Review expired permissions.', 'url': '', 'score': 0.6}
    poison = dict(source, doc_id='POL-099', source_type='test_fixture_prompt_injection', text=policy_text)
    monkeypatch.setattr(intelligence, 'search_knowledge', lambda query, filters, k: [source, poison])
    client = Mock()
    # Simulate the model trying to follow the malicious text. Strict output
    # validation rejects these unapproved control fields and uses sources only.
    output = intelligence._fallback([source], [])
    output.update(severity='low', recipients=['ops@example.net'])
    client.chat_json.return_value = output
    monkeypatch.setattr(intelligence, '_client', client)
    services.investigate.side_effect = attack_investigation
    services.analyze.side_effect = intelligence.analyze
    with workflow_services(services):
        result = run_incident_workflow()
        assert_protected(result, list_audit_events('INC-001'))
    system, task, untrusted = client.chat_json.call_args.args
    assert 'IGNORE ALL PREVIOUS INSTRUCTIONS' in untrusted['investigation:agent2']
    assert 'IGNORE ALL PREVIOUS INSTRUCTIONS' not in system + task
    assert all('POL-099' not in key for key in untrusted)


@pytest.mark.skipif(os.getenv('SENTINELAI_RUN_RAG_INTEGRATION') != '1', reason='Opt-in real embeddings')
def test_poisoned_real_index_log190_and_full_no_key_workflow(services, monkeypatch, tmp_path):
    from backend.rag.ingest import ingest
    from backend.rag.vector_store import get_collection
    monkeypatch.setattr(config, 'CHROMA_PERSIST_DIRECTORY', str(tmp_path / 'chroma'))
    monkeypatch.setattr(config, 'NEMOTRON_API_KEY', '')
    ingest(True)
    assert get_collection().get(where={'doc_id': 'POL-099'})['ids']
    services.investigate.side_effect = attack_investigation
    services.analyze.side_effect = intelligence.analyze
    with workflow_services(services):
        result = run_incident_workflow()
        audit = list_audit_events('INC-001')
        assert_protected(result, audit)
        assert intelligence.AI_UNAVAILABLE in result[0]['intelligence']['limitations']
        assert run_incident_workflow() == result
        assert services.store.connection.execute('SELECT count(*) FROM incidents').fetchone()[0] == 1
        assert any(a['action'] == 'retrieval' and a['details']['document_ids'] for a in audit)


@pytest.mark.skipif(os.getenv('SENTINELAI_RUN_RAG_INTEGRATION') != '1', reason='Opt-in real embeddings')
def test_real_p1_p2_p3_poisoned_index(initialized_store, monkeypatch, tmp_path):
    from backend import config
    from backend.rag.ingest import ingest
    from backend.security.audit import list_audit_events
    monkeypatch.setattr(config, 'NEMOTRON_API_KEY', '')
    monkeypatch.setattr(config, 'CHROMA_PERSIST_DIRECTORY', str(tmp_path / 'production-index'))
    assert ingest(True) == (12, 39, [])
    states = run_incident_workflow()
    assert len(states) == 1 and not states[0]['errors']
    state = states[0]
    assert state['final_report']['severity'] == 'high'
    assert {m['recipient_id'] for m in state['employee_matches']} == {'EMP-001', 'EMP-003', 'EMP-006'}
    encoded = json.dumps(state)
    assert 'POL-099' not in encoded and '@' not in encoded
    events = list_audit_events('INC-001')
    ids = set(next(e['details']['document_ids'] for e in events if e['action'] == 'retrieval'))
    assert 'MITRE-T1078' in ids and 'CASE-002' in ids
    assert ids & {'POL-001', 'POL-002', 'POL-003'}
    for group, items in state['intelligence'].items():
        if group != 'limitations':
            assert all(set(item['source_document_ids']) <= ids for item in items)
    assert run_incident_workflow() == states
