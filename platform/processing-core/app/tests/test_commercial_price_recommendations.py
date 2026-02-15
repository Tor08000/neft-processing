from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies.admin import require_admin_user
from app.api.v1.endpoints.commercial_price_recommendations import admin_router, router
from app.db import get_db
from app.fastapi_utils import generate_unique_id
from app.services.commercial_price_recommendations import ApplyRecommendationResult, SignalBundle, _decision


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
        revenue_7d=100000.0,
        decline_rate=0.2,
    )


def _policy() -> dict[str, float | bool]:
    return {
        "step_up": 0.3,
        "step_down": 0.2,
        "max_delta_per_day": 0.5,
        "target_margin_pct": 0.03,
        "min_volume_7d": 50,
        "min_revenue_7d": 50000,
        "elasticity_low_abs": 0.5,
        "elasticity_high_abs": 1.2,
        "high_decline_rate": 0.12,
        "min_confidence_to_change": 0.6,
        "guardrail_risk_zone_red": True,
        "guardrail_health_offline": True,
    }


def test_guardrails_offline_and_risk() -> None:
    offline = _base_signal()
    offline.health_status = "OFFLINE"
    assert _decision(offline, _policy())["action"] == "REVIEW_REQUIRED"

    red = _base_signal()
    red.risk_zone = "RED"
    out = _decision(red, _policy())
    assert out["action"] == "REVIEW_REQUIRED"
    assert out["reasons"] == ["RISK_RED"]


def test_core_logic_increase_and_decrease() -> None:
    inc = _decision(_base_signal(), _policy())
    assert inc["action"] == "INCREASE_PRICE"

    dec_signal = _base_signal()
    dec_signal.elasticity_score = -1.3
    dec_signal.margin_pct = 0.08
    dec_signal.decline_rate = 0.2
    dec = _decision(dec_signal, _policy())
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
                "station_lat": 55.75,
                "station_lon": 37.61,
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
                "policy_version": "v1",
                "status": "DRAFT",
                "decided_at": None,
                "decided_by": None,
            }
        ]

    monkeypatch.setattr("app.api.v1.endpoints.commercial_price_recommendations.list_price_recommendations", fake_list)
    monkeypatch.setattr("app.api.v1.endpoints.commercial_price_recommendations.get_station_price_recommendations", fake_list)
    monkeypatch.setattr("app.api.v1.endpoints.commercial_price_recommendations.update_recommendation_status", lambda *_, **__: True)

    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(router)
    app.include_router(admin_router)

    def _dummy_db():
        yield None

    app.dependency_overrides[get_db] = _dummy_db
    app.dependency_overrides[require_admin_user] = lambda: {"roles": ["NEFT_SUPERADMIN"], "sub": "admin@example.com"}
    client = TestClient(app)

    resp = client.get("/api/v1/commercial/recommendations/prices")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["id"] == "rec1"

    accept = client.post("/api/v1/admin/commercial/recommendations/prices/rec1/accept", json={"comment": "ok"})
    assert accept.status_code == 200
    assert accept.json()["status"] == "ACCEPTED"


def test_apply_recommendation_api(monkeypatch) -> None:
    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(router)
    app.include_router(admin_router)

    class _DummyDB:
        def __init__(self) -> None:
            self.commits = 0
            self.rollbacks = 0

        def commit(self) -> None:
            self.commits += 1

        def rollback(self) -> None:
            self.rollbacks += 1

    db = _DummyDB()

    def _dummy_db():
        yield db

    apply_calls: list[str] = []

    def fake_apply(*_, recommendation_id: str, **__):
        apply_calls.append(recommendation_id)
        return ApplyRecommendationResult(recommendation_id=recommendation_id, status="APPLIED", idempotent=len(apply_calls) > 1)

    monkeypatch.setattr("app.api.v1.endpoints.commercial_price_recommendations.apply_accepted_recommendation", fake_apply)

    app.dependency_overrides[get_db] = _dummy_db
    app.dependency_overrides[require_admin_user] = lambda: {"roles": ["NEFT_SUPERADMIN"], "sub": "admin@example.com"}
    client = TestClient(app)

    first = client.post("/api/v1/admin/commercial/recommendations/prices/rec1/apply", json={"comment": "ok"})
    second = client.post("/api/v1/admin/commercial/recommendations/prices/rec1/apply", json={"comment": "retry"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["status"] == "APPLIED"
    assert second.json()["status"] == "APPLIED"
    assert apply_calls == ["rec1", "rec1"]
    assert db.commits == 2


def test_apply_recommendation_api_validation_errors(monkeypatch) -> None:
    app = FastAPI(generate_unique_id_function=generate_unique_id)
    app.include_router(admin_router)

    class _DummyDB:
        def commit(self) -> None:
            return None

        def rollback(self) -> None:
            return None

    db = _DummyDB()

    def _dummy_db():
        yield db

    def fake_apply(*_, recommendation_id: str, **__):
        if recommendation_id == "bad-status":
            raise ValueError("recommendation_not_accepted")
        if recommendation_id == "no-product":
            raise ValueError("product_required")
        raise ValueError("recommendation_not_found")

    monkeypatch.setattr("app.api.v1.endpoints.commercial_price_recommendations.apply_accepted_recommendation", fake_apply)

    app.dependency_overrides[get_db] = _dummy_db
    app.dependency_overrides[require_admin_user] = lambda: {"roles": ["NEFT_SUPERADMIN"], "sub": "admin@example.com"}
    client = TestClient(app)

    bad_status = client.post("/api/v1/admin/commercial/recommendations/prices/bad-status/apply", json={})
    no_product = client.post("/api/v1/admin/commercial/recommendations/prices/no-product/apply", json={})
    missing = client.post("/api/v1/admin/commercial/recommendations/prices/missing/apply", json={})

    assert bad_status.status_code == 409
    assert no_product.status_code == 400
    assert missing.status_code == 404

