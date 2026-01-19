from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, Float, Index, Integer, JSON, String, Text, func

from app.db import Base
from app.db.types import ExistingEnum, GUID, new_uuid_str


class ExportJobReportType(str, Enum):
    CARDS = "cards"
    USERS = "users"
    TRANSACTIONS = "transactions"
    DOCUMENTS = "documents"
    AUDIT = "audit"
    SUPPORT = "support"
    SETTLEMENT_CHAIN = "settlement_chain"


class ExportJobFormat(str, Enum):
    CSV = "CSV"
    XLSX = "XLSX"
    ZIP = "ZIP"


class ExportJobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"


class ExportJob(Base):
    __tablename__ = "export_jobs"

    id = Column(GUID(), primary_key=True, default=new_uuid_str)
    org_id = Column(GUID(), nullable=False, index=True)
    created_by_user_id = Column(String(128), nullable=False, index=True)
    report_type = Column(ExistingEnum(ExportJobReportType, name="export_job_report_type"), nullable=False)
    format = Column(ExistingEnum(ExportJobFormat, name="export_job_format"), nullable=False)
    filters_json = Column(JSON, nullable=False, default={})
    status = Column(
        ExistingEnum(ExportJobStatus, name="export_job_status"),
        nullable=False,
        default=ExportJobStatus.QUEUED,
        index=True,
    )
    file_object_key = Column(Text, nullable=True)
    file_name = Column(String(255), nullable=True)
    content_type = Column(String(128), nullable=True)
    row_count = Column(Integer, nullable=True)
    processed_rows = Column(Integer, nullable=False, default=0)
    estimated_total_rows = Column(Integer, nullable=True)
    progress_percent = Column(Integer, nullable=True)
    progress_updated_at = Column(DateTime(timezone=True), nullable=True)
    avg_rows_per_sec = Column(Float, nullable=True)
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_export_jobs_org_created_at", "org_id", "created_at"),
        Index("ix_export_jobs_status", "status"),
    )


__all__ = [
    "ExportJob",
    "ExportJobFormat",
    "ExportJobReportType",
    "ExportJobStatus",
]
