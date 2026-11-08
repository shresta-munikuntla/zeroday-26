"""TEST ONLY: documented fixture owners, not P3 matching or delivery logic."""
OWNERS = [('EMP-001', 'DC-SRV-04'), ('EMP-003', 'DC-SRV-05'), ('EMP-006', 'DC-DB-01')]


def match_and_draft(report):
    return {'incident_id': report['incident_id'], 'employee_matches': [
        {'recipient_id': employee, 'asset_id': asset,
         'draft': f"Review {asset} for incident {report['incident_id']}; Security Incident Lead approval is required before delivery."}
        for employee, asset in OWNERS]}
