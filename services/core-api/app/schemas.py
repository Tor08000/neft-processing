# services/core-api/app/schemas.py
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, ConfigDict

# ===== Clients =====
class ClientCreate(BaseModel):
    name: str
    inn: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

class ClientOut(ClientCreate):
    id: UUID
    is_active: bool = True
    model_config = ConfigDict(from_attributes=True)

# ===== Cards =====
class CardCreate(BaseModel):
    client_id: UUID
    pan_masked: str
    token: str
    limit_daily: float = 0.0
    limit_monthly: float = 0.0

class CardOut(CardCreate):
    id: int
    is_active: bool = True
    model_config = ConfigDict(from_attributes=True)

# ===== AZS =====
class AzsCreate(BaseModel):
    code: str
    name: str
    address: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None

class AzsOut(AzsCreate):
    id: int
    is_active: bool = True
    model_config = ConfigDict(from_attributes=True)

# ===== Price List =====
class PriceListCreate(BaseModel):
    name: str
    fuel_type: str
    price: float

class PriceListOut(PriceListCreate):
    id: int
    is_active: bool = True
    model_config = ConfigDict(from_attributes=True)

# ===== Discount Rules =====
class DiscountRuleCreate(BaseModel):
    name: str
    priority: int = 100
    condition: str
    discount_percent: float = 0.0
    discount_abs: float = 0.0

class DiscountRuleOut(DiscountRuleCreate):
    id: int
    is_active: bool = True
    model_config = ConfigDict(from_attributes=True)

# ===== Transactions =====
class TransactionCreate(BaseModel):
    card_id: int
    azs_id: int
    fuel_type: str
    amount: float
    unit_price: float

class TransactionOut(BaseModel):
    id: int
    status: str
    total: float
