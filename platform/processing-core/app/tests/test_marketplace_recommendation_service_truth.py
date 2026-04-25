from __future__ import annotations

import pytest

from app.services.marketplace_recommendation_service import MarketplaceRecommendationService


class _DummyQuery:
    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def all(self):
        return []


class _DummyDB:
    def query(self, *args, **kwargs):
        return _DummyQuery()


def test_marketplace_recommendations_ml_mode_is_explicitly_degraded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RECOMMENDER_MODE", "ml")

    service = MarketplaceRecommendationService(_DummyDB())
    monkeypatch.setattr(
        service,
        "_fallback_recommendations",
        lambda *, limit: [{"product_id": "p-1", "score": 0, "reasons": [], "reason_codes": []}],
    )

    result = service.list_recommendations(tenant_id=None, client_id="client-1", limit=1)

    assert result.model == "catalog_fallback_v1"
    assert "ml_mode_requested_but_not_configured" in result.assumptions
    assert result.items[0]["product_id"] == "p-1"
