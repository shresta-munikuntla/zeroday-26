"""Strict native P1/P3 contracts and explicit workflow adapter contracts."""
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from backend.agents.intelligence_contract import InvestigationInput, IntelligenceOutput

Severity = Literal['low', 'medium', 'high', 'critical']
_evidence_readers = ContextVar('p1_evidence_readers', default=None)


class Agent1Output(BaseModel):
    model_config = ConfigDict(extra='allow', strict=True)
    incident_id: str = Field(pattern=r'^INC-\d+$')
    evidence_ids: list[str] = Field(min_length=1)
    reasons: list[str]


class Agent2Output(InvestigationInput):
    # Normalized fields supplied explicitly by the integration adapter.
    incident_id: str
    evidence_ids: list[str] = Field(min_length=1)
    permission_ids: list[str]
    affected_asset_ids: list[str] = Field(min_length=1)
    severity: Severity


Agent3Output = IntelligenceOutput


class EmployeeMatch(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    recipient_id: str
    asset_id: str
    draft: str


class Agent5Output(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    incident_id: str
    employee_matches: list[EmployeeMatch]


@contextmanager
def evidence_readers(event_exists, permission_exists):
    token = _evidence_readers.set((event_exists, permission_exists))
    try:
        yield
    finally:
        _evidence_readers.reset(token)


def check_evidence_ids(ids):
    readers = _evidence_readers.get()
    if readers is None:
        from backend.tools.security_queries import event_exists, permission_exists
        readers = (event_exists, permission_exists)
    event_exists, permission_exists = readers
    invalid = []
    for identifier in ids:
        if not isinstance(identifier, str):
            invalid.append(identifier)
        elif identifier.startswith('LOG-'):
            if not event_exists(identifier):
                invalid.append(identifier)
        elif identifier.startswith('PERM-'):
            if not permission_exists(identifier):
                invalid.append(identifier)
        else:
            invalid.append(identifier)
    return invalid


def check_document_ids(ids, retrieved_ids):
    retrieved = set(retrieved_ids)
    return [identifier for identifier in ids if identifier not in retrieved]


def cited_document_ids(intelligence):
    return [identifier for group, items in intelligence.items() if group != 'limitations'
            for item in items for identifier in item['source_document_ids']]


# Native teammate contracts are validated BEFORE adapting to workflow fields.
# The compact models above remain the explicit fixture/service adapter contract.
class NativeContract(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class TimeWindow(NativeContract):
    start: str
    end: str


class NativeAgent1Output(NativeContract):
    incident_id: str = Field(pattern=r'^INC-\d+$')
    detection_status: str
    summary: str
    severity_initial: Severity
    account_ids: list[str] = Field(min_length=1)
    source_ip_addresses: list[str] = Field(min_length=1)
    affected_asset_ids: list[str] = Field(min_length=1)
    time_window: TimeWindow
    evidence_ids: list[str] = Field(min_length=1)
    reasons: list[str]
    uncertainties: list[str]
    rules_triggered: list[str]


class TimelineEntry(NativeContract):
    timestamp: str
    description: str
    evidence_ids: list[str]


class AffectedAsset(NativeContract):
    asset_id: str
    asset_name: str
    criticality: Severity
    owner_team: str
    authorization: Literal['authorized', 'expired', 'none']
    permission_id: str | None
    successful_access_ids: list[str]
    denied_access_ids: list[str]


class NativeAgent2Output(NativeContract):
    incident_id: str = Field(pattern=r'^INC-\d+$')
    investigation_status: str
    timeline: list[TimelineEntry]
    affected_assets: list[AffectedAsset]
    potential_impact: str
    confirmed_facts: list[str]
    hypotheses: list[str]
    benign_explanations_to_check: list[str]
    checks_performed: list[str]
    severity: Severity
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(min_length=1)


class NativeAgent5Draft(BaseModel):
    # Database rows also carry delivery/approval metadata owned by P3.
    model_config = ConfigDict(extra='allow', strict=True)
    notification_id: str
    incident_id: str
    recipient_id: str
    recipient_channel: str
    asset_ids_json: str
    asset_ids: list[str] = Field(min_length=1)
    subject: str
    body: str
    status: Literal['draft', 'approved', 'sent', 'mocked', 'failed', 'rejected']


class GenerationInfo(NativeContract):
    mode: Literal['nemotron', 'fallback', 'unknown']
    model: str | None


class FinalReport(NativeContract):
    ai_generation: GenerationInfo | None = None
    incident_id: str
    status: Literal['investigating', 'awaiting_approval', 'incomplete']
    severity: Severity
    evidence_ids: list[str] = Field(min_length=1)
    affected_asset_ids: list[str] = Field(min_length=1)
    detection: Agent1Output
    investigation: Agent2Output
    intelligence: Agent3Output


def nested_evidence_ids(data):
    """Collect structured references, including timeline and per-asset evidence."""
    ids = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key in {'evidence_ids', 'permission_ids', 'successful_access_ids', 'denied_access_ids'}:
                ids.extend(value)
            elif key == 'permission_id' and value is not None:
                ids.append(value)
            elif isinstance(value, (dict, list)):
                ids.extend(nested_evidence_ids(value))
    elif isinstance(data, list):
        for item in data:
            ids.extend(nested_evidence_ids(item))
    return list(dict.fromkeys(ids))
