from __future__ import annotations

from pydantic import BaseModel, Field


class TerminalAuthRequest(BaseModel):
    merchant_id: str = Field(..., description="Идентификатор мерчанта")
    terminal_id: str = Field(..., description="Идентификатор терминала")
    client_id: str = Field(..., description="Идентификатор клиента")
    card_id: str = Field(..., description="Идентификатор карты")
    amount: float = Field(..., gt=0, description="Сумма операции")
    currency: str = Field(..., description="Валюта операции")


class TerminalAuthResponse(BaseModel):
    operation_id: str
    status: str
    limits: dict | None = None

    class Config:
        extra = "allow"


class TerminalCaptureRequest(BaseModel):
    auth_operation_id: str = Field(..., description="Идентификатор AUTH операции")
    amount: float | None = Field(None, description="Сумма к захвату")


class TerminalCaptureResponse(BaseModel):
    operation_id: str
    status: str
    approved: bool
    response_code: str
    response_message: str
