from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


PHASES = {"AUTH", "CAPTURE", "BOTH"}
ENTITY_TYPES = {"CLIENT", "CARD", "TERMINAL", "MERCHANT"}
SCOPES = {"PER_TX", "DAILY", "MONTHLY"}
PRODUCT_TYPES = {"ANY", "DIESEL", "AI92", "AI95", "AI98", "GAS", "OTHER"}


class LimitRuleBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    phase: str = "AUTH"

    client_id: str | None = None
    card_id: str | None = None
    merchant_id: str | None = None
    terminal_id: str | None = None

    entity_type: str = "CLIENT"
    scope: str = "PER_TX"
    product_type: str | None = None

    client_group_id: str | None = None
    card_group_id: str | None = None

    product_category: str | None = None
    mcc: str | None = None
    tx_type: str | None = None

    currency: str = "RUB"
    max_amount: int | None = None
    max_quantity: float | None = None
    daily_limit: int | None = None
    limit_per_tx: int | None = None

    active: bool = True

    @field_validator("phase")
    @classmethod
    def validate_phase(cls, v: str) -> str:
        if v not in PHASES:
            raise ValueError("phase must be one of AUTH, CAPTURE, BOTH")
        return v

    @field_validator("entity_type")
    @classmethod
    def validate_entity(cls, v: str) -> str:
        if v not in ENTITY_TYPES:
            raise ValueError("entity_type must be one of CLIENT, CARD, TERMINAL, MERCHANT")
        return v

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, v: str) -> str:
        if v not in SCOPES:
            raise ValueError("scope must be one of PER_TX, DAILY, MONTHLY")
        return v

    @field_validator("product_type")
    @classmethod
    def validate_product_type(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in PRODUCT_TYPES:
            raise ValueError("product_type must be a supported fuel type")
        return v


class LimitRuleCreate(LimitRuleBase):
    pass


class LimitRuleUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    entity_type: str | None = None
    scope: str | None = None
    product_type: str | None = None
    max_amount: int | None = None
    max_quantity: float | None = None
    daily_limit: int | None = None
    limit_per_tx: int | None = None

    active: bool | None = None

    @field_validator("phase")
    @classmethod
    def validate_phase(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in PHASES:
            raise ValueError("phase must be one of AUTH, CAPTURE, BOTH")
        return v

    @field_validator("entity_type")
    @classmethod
    def validate_entity(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in ENTITY_TYPES:
            raise ValueError("entity_type must be one of CLIENT, CARD, TERMINAL, MERCHANT")
        return v

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in SCOPES:
            raise ValueError("scope must be one of PER_TX, DAILY, MONTHLY")
        return v

    @field_validator("product_type")
    @classmethod
    def validate_product_type(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in PRODUCT_TYPES:
            raise ValueError("product_type must be a supported fuel type")
        return v


class LimitRuleRead(LimitRuleBase):
    id: int
    created_at: datetime


class LimitRuleListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[LimitRuleRead]
    total: int
    limit: int
    offset: int
