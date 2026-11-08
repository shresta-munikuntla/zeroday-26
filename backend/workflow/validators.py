"""Provisional contract validators pending spec §2; no fake runtime defaults."""
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from backend.agents.intelligence_contract import InvestigationInput, IntelligenceOutput

Severity = Literal['low', 'medium', 'high', 'critical']
_evidence_readers = ContextVar('p1_evidence_readers', default=None)


class Agent1Output(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    incident_id: str = Field(pattern=r'^INC-\d+$')
    evidence_ids: list[str] = Field(min_length=1)
    reasons: list[str]


class Agent2Output(InvestigationInput):
    # P1's real contract is absent. These required workflow fields are provisional.
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
        raise RuntimeError('Bind real P1 event_exists and permission_exists functions first')
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
