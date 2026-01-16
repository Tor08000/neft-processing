from __future__ import annotations

from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, Index, JSON, String, func

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str
from app.models.export_jobs import ExportJobFormat, ExportJobReportType


class ReportScheduleKind(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"


class ReportScheduleStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DISABLED = "DISABLED"


class ReportSchedule(Base):
    __tablename__ = "report_schedules"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    org_id = Column(GUID(), nullable=False, index=True)
    created_by_user_id = Column(String(128), nullable=False, index=True)
    report_type = Column(ExistingEnum(ExportJobReportType, name="export_job_report_type"), nullable=False)
    format = Column(ExistingEnum(ExportJobFormat, name="export_job_format"), nullable=False)
    filters_json = Column(JSON, nullable=False, default={})
    schedule_kind = Column(ExistingEnum(ReportScheduleKind, name="report_schedule_kind"), nullable=False)
    schedule_meta = Column(JSON, nullable=False, default={})
    timezone = Column(String(64), nullable=False, default="Europe/Moscow")
    delivery_in_app = Column(Boolean, nullable=False, default=True)
    delivery_email_to_creator = Column(Boolean, nullable=False, default=True)
    delivery_email_to_roles = Column(JSON, nullable=False, default=list)
    status = Column(
        ExistingEnum(ReportScheduleStatus, name="report_schedule_status"),
        nullable=False,
        default=ReportScheduleStatus.ACTIVE,
        index=True,
    )
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_report_schedules_org_status", "org_id", "status"),
        Index("ix_report_schedules_next_run_at", "next_run_at"),
    )


__all__ = [
    "ReportSchedule",
    "ReportScheduleKind",
    "ReportScheduleStatus",
]
