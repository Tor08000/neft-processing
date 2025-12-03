from datetime import datetime

from pydantic import BaseModel, validator


PHASES = {"AUTH", "CAPTURE", "BOTH"}


class LimitRuleBase(BaseModel):
    phase: str = "AUTH"

    client_id: str | None = None
    card_id: str | None = None
    merchant_id: str | None = None
    terminal_id: str | None = None

    client_group_id: str | None = None
    card_group_id: str | None = None

    product_category: str | None = None
    mcc: str | None = None
    tx_type: str | None = None

    currency: str = "RUB"
    daily_limit: int | None = None
    limit_per_tx: int | None = None

    active: bool = True

    @validator("phase")
    def validate_phase(cls, v: str) -> str:
        if v not in PHASES:
            raise ValueError("phase must be one of AUTH, CAPTURE, BOTH")
        return v

    class Config:
        orm_mode = True
        from_attributes = True


class LimitRuleCreate(LimitRuleBase):
    pass


class LimitRuleUpdate(BaseModel):
    phase: str | None = None

    client_id: str | None = None
    card_id: str | None = None
    merchant_id: str | None = None
    terminal_id: str | None = None

    client_group_id: str | None = None
    card_group_id: str | None = None

    product_category: str | None = None
    mcc: str | None = None
    tx_type: str | None = None

    currency: str | None = None
    daily_limit: int | None = None
    limit_per_tx: int | None = None

    active: bool | None = None

    @validator("phase")
    def validate_phase(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in PHASES:
            raise ValueError("phase must be one of AUTH, CAPTURE, BOTH")
        return v

    class Config:
        orm_mode = True
        from_attributes = True


class LimitRuleRead(LimitRuleBase):
    id: int
    created_at: datetime


class LimitRuleListResponse(BaseModel):
    items: list[LimitRuleRead]
    total: int
    limit: int
    offset: int

    class Config:
        orm_mode = True
        from_attributes = True
