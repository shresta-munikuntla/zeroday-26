"""Agent 3 JSON schema and its explicit investigation search input.

Architecture specifies the six output groups, while the repository's existing
P2 nested schema is retained for compatibility. Native P1/P3 schemas are in
workflow.validators; the external spec referenced by the architecture is absent.
"""
from pydantic import BaseModel, ConfigDict, Field, AliasChoices


class InvestigationInput(BaseModel):
    model_config = ConfigDict(extra='allow', strict=True)
    status: str = Field(validation_alias=AliasChoices('status', 'investigation_status'))
    confirmed_facts: list[str | dict]
    investigation_reasons: list[str] = Field(
        validation_alias=AliasChoices('investigation_reasons', 'reasons'))


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Technique(Contract):
    technique_id: str
    name: str
    relevance: str
    source_document_ids: list[str]


class Policy(Contract):
    policy_id: str
    section: str
    summary: str
    source_document_ids: list[str]


class HistoricalCase(Contract):
    case_id: str
    summary: str
    relevance: str
    source_document_ids: list[str]


class Action(Contract):
    action: str
    source_document_ids: list[str]


class Resource(Contract):
    title: str
    url: str
    source_document_ids: list[str]


class IntelligenceOutput(Contract):
    matched_techniques: list[Technique]
    policy_references: list[Policy]
    historical_cases: list[HistoricalCase]
    recommended_actions: list[Action]
    recommended_resources: list[Resource]
    limitations: list[str]
