"""Adapters between the landed P1/P3 contracts and the validated P2 workflow."""
from contextlib import contextmanager
from copy import deepcopy
import json

from backend.storage import connect, initialize
from backend.workflow.storage import evidence_key
from backend.workflow.validators import NativeAgent1Output, NativeAgent2Output, NativeAgent5Draft


class ApplicationWorkflowStore:
    """Persist workflow state and dashboard projection in the API's incident store."""
    def __init__(self, connection, native_connection=None):
        self.connection = connection
        self.native_connection = native_connection
        columns = {r[1] for r in connection.execute('PRAGMA table_info(incidents)')}
        for name in ('evidence_key', 'state_json', 'final_report_json'):
            if name not in columns:
                connection.execute(f'ALTER TABLE incidents ADD COLUMN {name} TEXT')
        connection.execute('CREATE UNIQUE INDEX IF NOT EXISTS incidents_evidence ON incidents(evidence_key)')
        connection.commit()

    def find(self, ids):
        row = self.connection.execute('SELECT state_json, approval_status, status FROM incidents WHERE evidence_key=?',
                                      (evidence_key(ids),)).fetchone()
        if not row or not row[0]:
            return None
        state = json.loads(row[0])
        state['approval_status'] = row[1]
        if state['final_report']:
            state['final_report']['status'] = row[2]
        return state

    def save(self, state, ids, status):
        from backend.agents.incident_workflow import dashboard_report
        existing = self.connection.execute('SELECT evidence_key FROM incidents WHERE incident_id=?',
                                           (state['incident_id'],)).fetchone()
        if existing and existing[0] and existing[0] != evidence_key(ids):
            raise ValueError('Incident ID is already bound to different evidence')
        if self.native_connection is not None:
            from backend.database.db import evidence_key as native_key
            native = self.native_connection
            previous = native.execute('SELECT evidence_key FROM incidents WHERE incident_id=?',
                                      (state['incident_id'],)).fetchone()
            if previous and previous[0] != native_key(ids):
                raise ValueError('P1 incident ID is bound to different evidence')
        report = deepcopy(state['final_report'])
        if report and state['investigation']:
            projection = dashboard_report(state)
            intelligence = state['intelligence'] or {}
            projection.update(report)
            projection.update({
                'recommended_actions': intelligence.get('recommended_actions', []),
                'mitre_techniques': intelligence.get('matched_techniques', []),
                'policy_references': intelligence.get('policy_references', []),
                'historical_cases': intelligence.get('historical_cases', []),
                'recommended_resources': intelligence.get('recommended_resources', []),
                'limitations': intelligence.get('limitations', []),
            })
            report = projection
        report = report or {'incident_id': state['incident_id'], 'status': status,
                            'errors': state['errors']}
        detection = state['detection'] or {}
        severity = (state['investigation'] or {}).get('severity', detection.get('severity_initial', 'unknown'))
        with self.connection:
            self.connection.execute('''INSERT INTO incidents
                (incident_id,severity,status,approval_status,summary,report_json,evidence_key,state_json,final_report_json)
                VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(incident_id) DO UPDATE SET
                severity=excluded.severity,status=excluded.status,summary=excluded.summary,
                report_json=excluded.report_json,state_json=excluded.state_json,
                final_report_json=excluded.final_report_json''',
                (state['incident_id'], severity, status, state['approval_status'], detection.get('summary',''),
                 json.dumps(report), evidence_key(ids), json.dumps(state),
                 json.dumps(state['final_report']) if state['final_report'] else None))
        # P1 owns ID assignment and deduplication. Persist the corresponding
        # incident using its existing schema/key convention so subsequent detect()
        # calls see saved IDs; no schema replacement or seed reset is involved.
        if self.native_connection is not None:
            from datetime import datetime, timezone
            from backend.database.db import evidence_key as native_key
            native = self.native_connection
            with native:
                native.execute('''INSERT INTO incidents
                    (incident_id,created_at,status,severity,summary,evidence_key,final_report_json)
                    VALUES (?,?,?,?,?,?,?) ON CONFLICT(incident_id) DO UPDATE SET
                    status=excluded.status,severity=excluded.severity,summary=excluded.summary,
                    final_report_json=excluded.final_report_json''',
                    (state['incident_id'], datetime.now(timezone.utc).isoformat(), status,
                     None if severity == 'unknown' else severity, detection.get('summary', ''),
                     native_key(ids), json.dumps(state['final_report']) if state['final_report'] else None))


def investigate_detection(detection):
    from backend.agents.investigation import investigate
    result = NativeAgent2Output.model_validate(investigate(detection)).model_dump()
    result['status'] = result['investigation_status']
    result['investigation_reasons'] = [detection['summary'], *detection['reasons']]
    result['permission_ids'] = [x for x in result['evidence_ids'] if x.startswith('PERM-')]
    result['affected_asset_ids'] = [a['asset_id'] for a in result['affected_assets']]
    return result


def draft_report(report):
    from backend.agents.employee_notification import match_and_draft
    drafts = match_and_draft(report)
    if not isinstance(drafts, list):
        raise ValueError('Agent 5 must return a list of drafts')
    drafts = [NativeAgent5Draft.model_validate(d).model_dump() for d in drafts]
    if any(d['incident_id'] != report['incident_id'] for d in drafts):
        raise ValueError('Agent 5 draft incident mismatch')
    return {'incident_id': report['incident_id'], 'employee_matches': [
        {'recipient_id': d['recipient_id'], 'asset_id': asset, 'draft': d['body']}
        for d in drafts for asset in d['asset_ids']]}



@contextmanager
def production_services():
    from backend.agents.threat_detection import detect
    from backend.database.db import db_path, get_connection
    from backend.database.seed import seed
    from backend.tools.security_queries import event_exists, permission_exists
    from backend.workflow.orchestrator import WorkflowServices
    from pathlib import Path
    path = Path(db_path())
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        seed(str(path))
    initialize()
    db = connect()
    native = get_connection()
    try:
        yield WorkflowServices(detect, investigate_detection, event_exists,
                               permission_exists, draft_report, ApplicationWorkflowStore(db, native),
                               detection_model=NativeAgent1Output)
    finally:
        native.close()
        db.close()
