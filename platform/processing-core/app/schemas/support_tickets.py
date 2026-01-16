from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.support_ticket import SupportTicketPriority, SupportTicketStatus


class SupportTicketCreate(BaseModel):
    subject: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1)
    priority: SupportTicketPriority = SupportTicketPriority.NORMAL


class SupportTicketCommentCreate(BaseModel):
    message: str = Field(..., min_length=1)


class SupportTicketCommentOut(BaseModel):
    user_id: str
    message: str
    created_at: datetime


class SupportTicketAttachmentInit(BaseModel):
    file_name: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=1, max_length=128)
    size: int = Field(..., ge=1)


class SupportTicketAttachmentComplete(BaseModel):
    object_key: str = Field(..., min_length=1)
    file_name: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=1, max_length=128)
    size: int = Field(..., ge=1)


class SupportTicketAttachmentInitResponse(BaseModel):
    upload_url: str
    object_key: str


class SupportTicketAttachmentOut(BaseModel):
    id: str
    ticket_id: str
    org_id: str
    uploaded_by_user_id: str
    file_name: str
    content_type: str
    size: int
    object_key: str
    created_at: datetime


class SupportTicketAttachmentListResponse(BaseModel):
    items: list[SupportTicketAttachmentOut]


class SupportTicketOut(BaseModel):
    id: str
    org_id: str
    created_by_user_id: str
    subject: str
    message: str
    status: SupportTicketStatus
    priority: SupportTicketPriority
    created_at: datetime
    updated_at: datetime


class SupportTicketDetail(SupportTicketOut):
    comments: list[SupportTicketCommentOut] = Field(default_factory=list)


class SupportTicketListResponse(BaseModel):
    items: list[SupportTicketOut]
    next_cursor: str | None = None


__all__ = [
    "SupportTicketCommentCreate",
    "SupportTicketCommentOut",
    "SupportTicketAttachmentComplete",
    "SupportTicketAttachmentInit",
    "SupportTicketAttachmentInitResponse",
    "SupportTicketAttachmentListResponse",
    "SupportTicketAttachmentOut",
    "SupportTicketCreate",
    "SupportTicketDetail",
    "SupportTicketListResponse",
    "SupportTicketOut",
]
