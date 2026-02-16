from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .common import ORMModel


class PipelineCreate(BaseModel):
    name: str
    is_default: bool = False


class PipelineUpdate(BaseModel):
    name: str | None = None
    is_default: bool | None = None


class StageCreate(BaseModel):
    name: str
    position: int
    is_won: bool = False
    is_lost: bool = False


class StageUpdate(BaseModel):
    name: str | None = None
    position: int | None = None
    is_won: bool | None = None
    is_lost: bool | None = None


class StageOut(ORMModel):
    id: str
    pipeline_id: str
    tenant_id: str
    name: str
    position: int
    is_won: bool
    is_lost: bool
    created_at: datetime


class PipelineOut(ORMModel):
    id: str
    tenant_id: str
    name: str
    is_default: bool
    created_at: datetime
    stages: list[StageOut] = Field(default_factory=list)


class PipelineListOut(BaseModel):
    items: list[PipelineOut]
    limit: int
    offset: int
    total: int
