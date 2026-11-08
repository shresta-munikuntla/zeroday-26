from copy import deepcopy
import json
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from backend.security.audit import list_audit_events, write_audit_event
from backend.workflow.orchestrator import run_incident_workflow, workflow_services
from backend.workflow.state import IncidentState
from backend.workflow.validators import (Agent1Output, Agent2Output, Agent3Output, Agent5Output,
                                         check_evidence_ids, check_document_ids)
from backend.tests.fakes import agent1, agent2


def test_success_order_persistence_audit_and_idempotency(services):
    order = Mock()
    for name in ('detect', 'investigate', 'analyze', 'match_and_draft'):
        order.attach_mock(getattr(services, name), name)
    with workflow_services(services):
        result = run_incident_workflow()
        assert len(result) == 1
        state = result[0]
        assert set(state) == set(IncidentState.__annotations__)
        assert state['incident_id'] == 'INC-001'
        assert state['approval_status'] == 'pending'
        assert state['notification_status'] == 'not_sent'
        assert state['errors'] == []
        assert state['final_report']['severity'] == 'high'
        assert state['final_report']['status'] == 'awaiting_approval'
        assert [c[0] for c in order.mock_calls] == ['detect', 'investigate', 'analyze', 'match_and_draft']
        row = services.store.connection.execute('SELECT status, final_report_json FROM incidents').fetchone()
        assert row[0] == 'awaiting_approval'
        assert json.loads(row[1]) == state['final_report']
        audits = list_audit_events('INC-001')
        stages = [a for a in audits if a['action'] != 'validation']
        assert [a['action'] for a in stages] == ['detection', 'investigation', 'retrieval', 'intelligence', 'report_generation', 'notification_drafting', 'final_status']
        assert stages[0]['details']['evidence_ids'] == agent1.DETECTION['evidence_ids']
        assert stages[1]['details']['evidence_ids'][-1] == 'PERM-003'
        assert stages[2]['details']['document_ids'] == ['POL-003']
        assert all(a['actor_type'] == 'agent' and a['timestamp'] for a in audits)
        repeated = run_incident_workflow()
        assert repeated == result
        assert services.investigate.call_count == 1
        assert services.match_and_draft.call_count == 1
        # Different incident label and reversed evidence must still reuse INC-001.
        duplicate = deepcopy(agent1.DETECTION)
        duplicate['incident_id'] = 'INC-002'
        duplicate['evidence_ids'].reverse()
        services.detect.side_effect = None
        services.detect.return_value = [duplicate]
        assert run_incident_workflow()[0]['incident_id'] == 'INC-001'
        assert services.store.connection.execute('SELECT count(*) FROM incidents').fetchone()[0] == 1


def test_evidence_helpers(services):
    with workflow_services(services):
        assert check_evidence_ids(['LOG-101', 'PERM-003', 'LOG-999', 'PERM-999', 'OTHER']) == ['LOG-999', 'PERM-999', 'OTHER']
        assert check_document_ids(['POL-003', 'POL-099'], ['POL-003']) == ['POL-099']
        services.event_exists.assert_any_call('LOG-999')
        services.permission_exists.assert_any_call('PERM-999')


def test_fake_evidence_stops_before_investigation(services):
    bad = deepcopy(agent1.DETECTION)
    bad['evidence_ids'].append('LOG-999')
    services.detect.side_effect = None
    services.detect.return_value = [bad]
    with workflow_services(services):
        state = run_incident_workflow()[0]
        assert state['errors']
        assert state['investigation'] is None and state['intelligence'] is None
        assert state['final_report'] is None
        services.investigate.assert_not_called()
        assert services.store.connection.execute('SELECT status FROM incidents').fetchone()[0] == 'incomplete'
        assert any(a['action'] == 'error' for a in list_audit_events('INC-001'))


@pytest.mark.parametrize('component', ['investigate', 'analyze', 'match_and_draft'])
def test_failure_preserves_completed_work_and_continues(services, component):
    second = deepcopy(agent1.DETECTION)
    second['incident_id'] = 'INC-002'
    second['evidence_ids'] = ['LOG-190']
    services.detect.side_effect = None
    services.detect.return_value = [agent1.DETECTION, second]
    original = getattr(services, component).side_effect
    calls = 0
    def fail_once(argument):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError('SECRET credential must never appear in errors')
        return original(argument)
    getattr(services, component).side_effect = fail_once
    with workflow_services(services):
        first, other = run_incident_workflow()
        assert first['errors'] and 'SECRET' not in json.dumps(first)
        assert other['errors'] == []
        assert other['final_report']['status'] == 'awaiting_approval'
        assert services.store.connection.execute("SELECT status FROM incidents WHERE incident_id='INC-001'").fetchone()[0] == 'incomplete'
        if component == 'analyze':
            assert first['investigation'] is not None and first['intelligence'] is None
        if component == 'match_and_draft':
            assert first['intelligence'] is not None and first['employee_matches'] is None
            assert first['final_report']['status'] == 'incomplete'
        assert 'SECRET' not in json.dumps(list_audit_events('INC-001'))


@pytest.mark.parametrize('component,invalid', [
    ('investigate', {}), ('analyze', {}), ('match_and_draft', {}),
])
def test_missing_contract_fields_not_accepted(services, component, invalid):
    getattr(services, component).side_effect = None
    getattr(services, component).return_value = invalid
    with workflow_services(services):
        state = run_incident_workflow()[0]
        assert state['errors']
        assert services.store.connection.execute('SELECT status FROM incidents').fetchone()[0] == 'incomplete'


def test_unretrieved_intelligence_citation_rejected(services):
    from backend.agents.intelligence import _fallback
    output = _fallback([], [])
    output['recommended_actions'] = [{'action': 'Review', 'source_document_ids': ['POL-999']}]
    services.analyze.side_effect = None
    services.analyze.return_value = output
    with workflow_services(services):
        state = run_incident_workflow()[0]
        assert state['errors'] and state['intelligence'] is None
        services.match_and_draft.assert_not_called()


def test_audit_does_not_store_credentials_or_employee_records(services, monkeypatch):
    from backend import config
    monkeypatch.setattr(config, 'NEMOTRON_API_KEY', 'secret-key-value')
    with workflow_services(services):
        write_audit_event('INC-001', 'agent', 'test', 'test', 'incident', 'INC-001', {
            'api_key': 'secret-key-value', 'employee': {'name': 'Private Name'},
            'status': 'secret-key-value person@example.net', 'evidence_ids': ['LOG-101']})
        encoded = json.dumps(list_audit_events('INC-001'))
        assert 'secret-key-value' not in encoded and 'Private Name' not in encoded
        assert 'person@example.net' not in encoded
        assert 'LOG-101' in encoded


def test_default_workflow_uses_real_agents(initialized_store, monkeypatch, tmp_path):
    from backend import config
    from backend.storage import connect
    from backend.security.audit import list_audit_events
    monkeypatch.setattr(config, 'NEMOTRON_API_KEY', '')
    monkeypatch.setattr(config, 'CHROMA_PERSIST_DIRECTORY', str(tmp_path / 'empty-index'))
    states = run_incident_workflow()
    assert len(states) == 1
    state = states[0]
    assert state['incident_id'] == 'INC-001' and not state['errors']
    assert state['final_report']['status'] == 'awaiting_approval'
    assert state['final_report']['severity'] == 'high'
    assert {m['recipient_id'] for m in state['employee_matches']} == {'EMP-001', 'EMP-003', 'EMP-006'}
    assert 'No relevant source was retrieved.' in state['intelligence']['limitations']
    assert run_incident_workflow() == states
    with connect() as db:
        assert db.execute('SELECT count(*) FROM incidents').fetchone()[0] == 1
        assert db.execute('SELECT count(*) FROM notifications').fetchone()[0] == 3
        assert db.execute('SELECT final_report_json FROM incidents').fetchone()[0]
    assert {'detection', 'investigation', 'retrieval', 'intelligence', 'report_generation',
            'notification_drafting', 'final_status'} <= {e['action'] for e in list_audit_events('INC-001')}
    assert '@' not in json.dumps(states)



def test_detection_failure_is_audited_without_inventing_incident(services):
    services.detect.side_effect = TimeoutError('private details')
    with workflow_services(services):
        with pytest.raises(RuntimeError, match='Detection failed'):
            run_incident_workflow()
    assert services.store.connection.execute('SELECT count(*) FROM incidents').fetchone()[0] == 0
    assert services.store.connection.execute('SELECT action FROM audit_events').fetchone()[0] == 'error'


def test_same_incident_id_cannot_overwrite_different_evidence(services):
    with workflow_services(services):
        original = run_incident_workflow()[0]
        changed = deepcopy(agent1.DETECTION)
        changed['evidence_ids'] = ['LOG-190']
        services.detect.side_effect = None
        services.detect.return_value = [changed]
        failed = run_incident_workflow()[0]
        assert failed['errors']
        row = services.store.connection.execute('SELECT state_json FROM incidents').fetchone()
        assert json.loads(row[0]) == original


def test_investigation_fake_permission_and_omitted_evidence_rejected(services):
    def invalid(detection):
        data = agent2.investigate(detection)
        data['permission_ids'].append('PERM-999')
        return data
    services.investigate.side_effect = invalid
    with workflow_services(services):
        result = run_incident_workflow()[0]
        assert result['errors'] and result['investigation'] is None
        services.analyze.assert_not_called()


def test_agent5_cannot_return_unaffected_asset(services):
    services.match_and_draft.side_effect = None
    services.match_and_draft.return_value = {'incident_id': 'INC-001', 'employee_matches': [
        {'recipient_id': 'EMP-001', 'asset_id': 'DC-SRV-99', 'draft': 'Invalid'}]}
    with workflow_services(services):
        state = run_incident_workflow()[0]
        assert state['errors'] and state['employee_matches'] is None
        assert state['final_report']['status'] == 'incomplete'


def test_native_p1_contracts_validate_all_required_fields(detections, investigation):
    from pydantic import ValidationError
    from backend.workflow.validators import NativeAgent1Output, NativeAgent2Output
    NativeAgent1Output.model_validate(detections[0])
    NativeAgent2Output.model_validate(investigation)
    for field in NativeAgent1Output.model_fields:
        broken = deepcopy(detections[0])
        del broken[field]
        with pytest.raises(ValidationError):
            NativeAgent1Output.model_validate(broken)
    for field in NativeAgent2Output.model_fields:
        broken = deepcopy(investigation)
        del broken[field]
        with pytest.raises(ValidationError):
            NativeAgent2Output.model_validate(broken)
    broken = deepcopy(investigation)
    broken['timeline'][0]['evidence_ids'] = 'LOG-101'
    with pytest.raises(ValidationError):
        NativeAgent2Output.model_validate(broken)


def test_nested_fake_evidence_stops_workflow(services):
    def invalid(detection):
        result = agent2.investigate(detection)
        result['timeline'] = [{'evidence_ids': ['LOG-999']}]
        return result
    services.investigate.side_effect = invalid
    with workflow_services(services):
        state = run_incident_workflow()[0]
        assert state['errors'] and state['investigation'] is None
        services.analyze.assert_not_called()
        assert any(event['action'] == 'validation_rejected' for event in list_audit_events('INC-001'))


def test_native_agent2_can_be_analyzed_directly(investigation, monkeypatch):
    from backend.agents import intelligence
    monkeypatch.setattr(intelligence, 'search_knowledge', lambda *args, **kwargs: [])
    result = intelligence.analyze(investigation)
    assert intelligence.NO_SOURCES in result['limitations']


def test_production_persists_p1_incident_key(initialized_store, monkeypatch, tmp_path):
    from backend.database.seed import seed
    from backend.database.db import find_incident_by_evidence, next_incident_number
    from backend import config
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{tmp_path / "p1.db"}')
    seed()
    monkeypatch.setattr(config, 'CHROMA_PERSIST_DIRECTORY', str(tmp_path / 'missing'))
    state = run_incident_workflow()[0]
    assert not state['errors']
    assert find_incident_by_evidence(state['detection']['evidence_ids']) == 'INC-001'
    assert next_incident_number() == 2
    assert run_incident_workflow()[0]['incident_id'] == 'INC-001'


def test_environment_example_is_secret_free():
    from backend import config
    for line in (config.ROOT / '.env.example').read_text().splitlines():
        if line.strip() and not line.lstrip().startswith('#'):
            key, separator, value = line.partition('=')
            assert separator and not value.strip(), f'{key} should be empty in the example'


def test_production_detector_failure_has_global_audit(initialized_store, monkeypatch):
    from backend.agents import threat_detection
    monkeypatch.setattr(threat_detection, 'detect', Mock(side_effect=TimeoutError('private prompt')))
    with pytest.raises(RuntimeError, match='Detection failed'):
        run_incident_workflow()
    events = list_audit_events(None)
    assert any(e['action'] == 'error' and e['details']['step'] == 'detection' for e in events)
    assert 'private prompt' not in json.dumps(events)
