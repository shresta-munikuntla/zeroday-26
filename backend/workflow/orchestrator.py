"""Sequential P2 workflow with explicitly bound P1/P3 and persistence adapters.

No production agent fake or test schema is imported here. See workflow_services
and docs/p2-contracts.md for the provisional integration boundary.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass
from typing import Callable

from backend.agents.intelligence import analyze as intelligence_analyze
from backend.rag.vector_store import capture_sources
from backend.security.audit import audit_connection, write_audit_event
from backend.workflow.state import IncidentState, initial_state
from backend.workflow.validators import (Agent1Output, Agent2Output, Agent3Output, Agent5Output,
    check_evidence_ids, check_document_ids, cited_document_ids, evidence_readers)


@dataclass
class WorkflowServices:
    detect: Callable
    investigate: Callable
    event_exists: Callable
    permission_exists: Callable
    match_and_draft: Callable
    store: object
    analyze: Callable = intelligence_analyze


_services = ContextVar('workflow_services', default=None)


@contextmanager
def workflow_services(services: WorkflowServices):
    """Bind real integrations (or explicit test fakes) for this request only."""
    token = _services.set(services)
    try:
        with audit_connection(services.store.connection), evidence_readers(
                services.event_exists, services.permission_exists):
            yield
    finally:
        _services.reset(token)


def _audit(identifier, action, details, actor='orchestrator'):
    write_audit_event(identifier, 'agent', actor, action, 'incident', identifier, details)


def run_incident_workflow() -> list[IncidentState]:
    services = _services.get()
    if services is None:
        raise RuntimeError('Bind real P1/P3 functions and an existing SQLiteWorkflowStore using workflow_services')
    try:
        detections = services.detect()
        if not isinstance(detections, list):
            raise ValueError('Detection must return a list of incidents')
    except Exception as error:
        _audit(None, 'error', {'step': 'detection', 'error_type': type(error).__name__})
        # No incident can be invented when detection itself failed.
        raise RuntimeError('Detection failed; no incident results are available') from None
    results = []
    for raw_detection in detections:
        identifier = raw_detection.get('incident_id', '') if isinstance(raw_detection, dict) else ''
        state = initial_state(identifier if isinstance(identifier, str) else '')
        evidence_ids = []
        step = 'detection_validation'
        try:
            detection = Agent1Output.model_validate(raw_detection).model_dump()
            evidence_ids = detection['evidence_ids']
            state['incident_id'] = detection['incident_id']
            state['detection'] = detection
            step = 'deduplication'
            existing = services.store.find(evidence_ids)
            if existing is not None:
                _audit(existing['incident_id'], 'incident_reused', {'evidence_ids': evidence_ids, 'reused': True})
                results.append(existing)
                continue
            step = 'detection_evidence_validation'
            if check_evidence_ids(evidence_ids):
                raise ValueError('Detection contains invalid evidence IDs')
            services.store.save(state, evidence_ids, 'detected')
            _audit(state['incident_id'], 'detection', {'evidence_ids': evidence_ids}, 'agent1')

            step = 'investigation'
            investigation = Agent2Output.model_validate(services.investigate(deepcopy(detection))).model_dump()
            # Keep optional raw context only for the untrusted model input. It
            # must not leak log banners or addresses into reports/state/drafts.
            agent_input = deepcopy(investigation)
            investigation = {key: value for key, value in investigation.items()
                             if key in Agent2Output.model_fields}
            if investigation['incident_id'] != state['incident_id']:
                raise ValueError('Investigation incident ID mismatch')
            if not set(evidence_ids) <= set(investigation['evidence_ids']):
                raise ValueError('Investigation omitted detection evidence')
            all_ids = investigation['evidence_ids'] + investigation['permission_ids']
            if check_evidence_ids(all_ids):
                raise ValueError('Investigation contains invalid evidence IDs')
            state['investigation'] = investigation
            services.store.save(state, evidence_ids, 'investigating')
            _audit(state['incident_id'], 'investigation', {
                'evidence_ids': all_ids, 'severity': investigation['severity']}, 'agent2')

            step = 'intelligence'
            with capture_sources() as sources:
                try:
                    raw_intelligence = services.analyze(agent_input)
                finally:
                    _audit(state['incident_id'], 'retrieval', {
                        'document_ids': sorted({s['doc_id'] for s in sources})}, 'agent3')
            intelligence = Agent3Output.model_validate(raw_intelligence).model_dump()
            retrieved_ids = {s['doc_id'] for s in sources}
            if check_document_ids(cited_document_ids(intelligence), retrieved_ids):
                raise ValueError('Intelligence contains unretrieved citations')
            if any(not action['source_document_ids'] for action in intelligence['recommended_actions']):
                raise ValueError('Recommendation missing supporting sources')
            state['intelligence'] = intelligence
            services.store.save(state, evidence_ids, 'investigating')
            _audit(state['incident_id'], 'intelligence', {'document_ids': sorted(retrieved_ids)}, 'agent3')

            step = 'report_generation'
            state['final_report'] = {
                'incident_id': state['incident_id'], 'status': 'investigating',
                'severity': investigation['severity'], 'evidence_ids': investigation['evidence_ids'],
                'affected_asset_ids': investigation['affected_asset_ids'],
                'detection': deepcopy(detection), 'investigation': deepcopy(investigation),
                'intelligence': deepcopy(intelligence),
            }
            services.store.save(state, evidence_ids, 'investigating')
            _audit(state['incident_id'], 'report_generation', {
                'severity': investigation['severity'], 'evidence_ids': investigation['evidence_ids']})

            step = 'notification_drafting'
            employees = Agent5Output.model_validate(
                services.match_and_draft(deepcopy(state['final_report']))).model_dump()
            if employees['incident_id'] != state['incident_id']:
                raise ValueError('Employee result incident ID mismatch')
            if any(item['asset_id'] not in investigation['affected_asset_ids']
                   for item in employees['employee_matches']):
                raise ValueError('Employee result references an unaffected asset')
            # Only deterministic P3 determines recipients; no model value is used.
            state['employee_matches'] = employees['employee_matches']
            _audit(state['incident_id'], 'notification_drafting', {
                'recipient_ids': [item['recipient_id'] for item in state['employee_matches']],
                'asset_ids': [item['asset_id'] for item in state['employee_matches']]}, 'agent5')

            step = 'final_status'
            state['final_report']['status'] = 'awaiting_approval'
            services.store.save(state, evidence_ids, 'awaiting_approval')
            _audit(state['incident_id'], 'final_status', {'status': 'awaiting_approval'})
        except Exception as error:
            # Exception text can contain secrets or raw records. Record the step
            # and class only, preserving completed validated work without leaks.
            state['errors'].append(f'{step} failed ({type(error).__name__})')
            if state['final_report'] is not None:
                state['final_report']['status'] = 'incomplete'
            try:
                _audit(state['incident_id'] or None, 'error', {
                    'step': step, 'error_type': type(error).__name__,
                    'evidence_ids': evidence_ids})
            except Exception:
                state['errors'].append('audit_write failed')
            if state['incident_id']:
                try:
                    services.store.save(state, evidence_ids, 'incomplete')
                    _audit(state['incident_id'], 'final_status', {'status': 'incomplete'})
                except Exception:
                    state['errors'].append('incomplete_persistence failed')
        results.append(state)
    return results
