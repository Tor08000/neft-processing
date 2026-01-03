from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.erp_stub import ErpStubExportStatus, ErpStubExportType


class ErpStubExportCreateRequest(BaseModel):
    export_type: ErpStubExportType
    entity_ids: list[str] | None = None
    period_from: datetime | None = None
    period_to: datetime | None = None
    export_ref: str | None = None


class ErpStubExportItemResponse(BaseModel):
    entity_type: str
    entity_id: str
    snapshot_json: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ErpStubExportResponse(BaseModel):
    id: str
    tenant_id: int
    export_ref: str
    export_type: ErpStubExportType
    payload_hash: str
    status: ErpStubExportStatus
    created_at: datetime
    updated_at: datetime
    items: list[ErpStubExportItemResponse]

    model_config = ConfigDict(from_attributes=True)


__all__ = [
    "ErpStubExportCreateRequest",
    "ErpStubExportItemResponse",
    "ErpStubExportResponse",
]
