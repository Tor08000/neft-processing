from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints.commercial_price_recommendations import admin_router, router
from app.api.dependencies.admin import require_admin_user
from app.db import get_db
from app.fastapi_utils import generate_unique_id
from app.services.commercial_price_recommendations import SignalBundle, _decision


def _base_signal() -> SignalBundle:
    return SignalBundle(
        station_id="1",
        product_code="AI95",
        current_price=60.0,
        elasticity_score=-0.3,
        elasticity_confidence=0.8,
        margin_pct=0.01,
        health_status="ONLINE",
        risk_zone="GREEN",
        volume_7d=4000.0,
        decline_rate=0.2,
    )


def test_guardrails_offline_and_risk() -> None:
    policy = {
        "min_confidence": 0.4,
        "min_volume_7d": 2000,
        "low_elasticity_abs": 0.5,
        "margin_target_pct": 0.03,
        "high_elasticity_threshold": -1.2,
        "high_decline_rate": 0.12,
        "step_up": 0.3,
        "step_down": 0.2,
        "max_delta_per_day": 0.5,
    }
    offline = _base_signal()
    offline.health_status = "OFFLINE"
    assert _decision(offline, policy)["action"] == "REVIEW_REQUIRED"

    red = _base_signal()
    red.risk_zone = "RED"
    out = _decision(red, policy)
    assert out["action"] == "REVIEW_REQUIRED"
    assert out["reasons"] == ["RISK_RED"]


def test_core_logic_increase_and_decrease() -> None:
    policy = {
        "min_confidence": 0.4,
        "min_volume_7d": 2000,
        "low_elasticity_abs": 0.5,
        "margin_target_pct": 0.03,
        "high_elasticity_threshold": -1.2,
        "high_decline_rate": 0.12,
        "step_up": 0.3,
        "step_down": 0.2,
        "max_delta_per_day": 0.5,
    }
    inc = _decision(_base_signal(), policy)
    assert inc["action"] == "INCREASE_PRICE"

    dec_signal = _base_signal()
    dec_signal.elasticity_score = -1.3
    dec_signal.margin_pct = 0.08
    dec_signal.decline_rate = 0.2
    dec = _decision(dec_signal, policy)
    assert dec["action"] == "DECREASE_PRICE"


def test_recommendations_api_routes(monkeypatch) -> None:
    now = datetime.now(tz=timezone.utc).replace(microsecond=0)

    def fake_list(*args, **kwargs):
        return [
            {
                "id": "rec1",
                "created_at": now.isoformat(),
                "station_id": "1",
                "station_name": "S",
                "station_address": "Addr",
                "risk_zone": "GREEN",
                "health_status": "ONLINE",
                "product_code": "AI95",
                "current_price": 60.0,
                "recommended_price": 60.3,
                "delta_price": 0.3,
                "action": "INCREASE",
                "confidence": 0.8,
                "reasons": ["LOW_ELASTICITY", "LOW_MARGIN"],
                "expected_volume_change_pct": -0.01,
                "expected_margin_change": None,
                "policy_version": "price-rec-v1",
                "status": "DRAFT",
            }
        ]

    monkeypatch.setattr("app.api.v1.endpoints.commercial_price_recommendations.list_price_recommendations", fake_list)
    monkeypatch.setattr("app.api.v1.endpoints.commercial_price_recommendations.get_station_price_recommendations", fake_list)
    monkeypatch.setattr("app.api.v1.endpoints.commercial_price_recommendations.update_recommendation_status", lambda *_: True)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(router)
    app.include_router(admin_router)

    def _dummy_db():
        yield None

    app.dependency_overrides[get_db] = _dummy_db
    app.dependency_overrides[require_admin_user] = lambda: {"roles": ["NEFT_SUPERADMIN"]}
    client = TestClient(app)

    resp = client.get("/api/v1/commercial/recommendations/prices")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["id"] == "rec1"

    accept = client.post("/api/v1/admin/commercial/recommendations/rec1/accept")
    assert accept.status_code == 200
    assert accept.json()["status"] == "ACCEPTED"
