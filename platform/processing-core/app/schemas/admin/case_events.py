from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.cases import CaseKind, CasePriority, CaseQueue, CaseSlaState, CaseStatus


class CaseEventActor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    email: str | None = None


class CaseEventChange(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    field: str
    before: Any = Field(alias="from")
    after: Any = Field(alias="to")


class CaseEventArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    id: str
    url: str | None = None


class CaseEventMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changes: list[CaseEventChange] | None = None
    reason: Any | None = None
    export_ref: CaseEventArtifact | None = None


class CaseEventOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    at: datetime
    type: str
    actor: CaseEventActor | None = None
    request_id: str | None = None
    trace_id: str | None = None
    source: str | None = None
    prev_hash: str | None = None
    hash: str | None = None
    signature: str | None = None
    signature_alg: str | None = None
    signing_key_id: str | None = None
    signed_at: datetime | None = None
    meta: CaseEventMeta | None = None


class CaseEventsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CaseEventOut]
    next_cursor: str | None = None


class CaseEventsVerifyChain(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    tail_hash: str | None = None
    count: int
    broken_index: int | None = None
    expected_hash: str | None = None
    actual_hash: str | None = None


class CaseEventsVerifySignatures(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    broken_index: int | None = None
    key_id: str | None = None


class CaseEventsVerifyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chain: CaseEventsVerifyChain
    signatures: CaseEventsVerifySignatures


class CaseStatusUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str


class CaseCloseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolution_note: str | None = None
    resolution_code: str | None = None


class CaseWithEventResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    tenant_id: int
    kind: CaseKind
    entity_id: str | None
    kpi_key: str | None
    window_days: int | None
    title: str
    status: CaseStatus
    queue: CaseQueue
    priority: CasePriority
    escalation_level: int
    first_response_due_at: datetime | None = None
    resolve_due_at: datetime | None = None
    sla_state: CaseSlaState | None = None
    created_by: str | None
    assigned_to: str | None
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime
    event: CaseEventOut | None = None
