from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.schemas.crm import CRMContractOut, CRMFeatureFlagOut, CRMProfileOut, CRMRiskProfileOut, CRMTariffOut


class CRMDecisionContextResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: str
    tenant_id: int
    active_contract: CRMContractOut | None
    tariff: CRMTariffOut | None
    feature_flags: list[CRMFeatureFlagOut]
    risk_profile: CRMRiskProfileOut | None
    limit_profile: CRMProfileOut | None
    enforcement_flags: dict[str, bool]


__all__ = ["CRMDecisionContextResponse"]
