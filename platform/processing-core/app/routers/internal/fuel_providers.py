from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.integrations.fuel.providers.adapter_registry import get_provider, load_default_providers
from app.integrations.fuel.providers.protocols import AuthorizeRequest
from app.schemas.fuel_provider import ProviderRefAuthorizeRequest, ProviderRefAuthorizeResponse

router = APIRouter(prefix="/internal/fuel/providers", tags=["fuel-providers"])


@router.post("/provider_ref/authorize", response_model=ProviderRefAuthorizeResponse)
def provider_ref_authorize(payload: ProviderRefAuthorizeRequest, db: Session = Depends(get_db)):
    load_default_providers()
    adapter = get_provider("provider_ref")
    result = adapter.authorize(
        db,
        AuthorizeRequest(
            client_id=None,
            card_id=None,
            vehicle_id=None,
            merchant_id=None,
            station_id=payload.station_id,
            amount=str(payload.amount),
            currency=payload.currency,
            product_code=payload.product_code,
            timestamp=payload.ts,
            offline_mode_allowed=payload.offline_mode_allowed,
            context=payload.context,
            provider_tx_id=payload.tx_id,
            card_token=payload.card_token,
        ),
    )
    return ProviderRefAuthorizeResponse(
        decision=result.decision,
        reason_code=result.reason_code,
        auth_code=result.auth_code,
        offline_profile=result.offline_profile,
    )
