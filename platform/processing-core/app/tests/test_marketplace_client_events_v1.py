from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.models.marketplace_client_events import (
    MarketplaceClientEntityType,
    MarketplaceClientEvent,
    MarketplaceClientEventSource,
    MarketplaceClientEventType,
)
from app.routers.marketplace_client_events import router as client_events_router
from app.security.client_auth import require_client_user


CURRENT_TOKEN: dict | None = None


def _token_for_client(client_id: str) -> dict:
    return {"client_id": client_id, "user_id": str(uuid4()), "tenant_id": 1}


def _create_event(
    db: Session,
    *,
    client_id: str,
    event_type: MarketplaceClientEventType,
    entity_type: MarketplaceClientEntityType,
    entity_id: str | None,
    ts: datetime,
) -> MarketplaceClientEvent:
    event = MarketplaceClientEvent(
        id=str(uuid4()),
        client_id=client_id,
        tenant_id=1,
        user_id=str(uuid4()),
        session_id="session-1",
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        source=MarketplaceClientEventSource.CLIENT_PORTAL,
        page="/marketplace",
        payload={"source": "test"},
        ts=ts,
    )
    db.add(event)
    db.commit()
    return event


def _make_client() -> tuple[TestClient, sessionmaker]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)

    MarketplaceClientEvent.__table__.create(bind=engine)

    app = FastAPI()
    app.include_router(client_events_router, prefix="/api")

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_require_client_user() -> dict:
        if CURRENT_TOKEN is None:
            raise RuntimeError("token_not_set")
        return CURRENT_TOKEN

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[require_client_user] = override_require_client_user

    return TestClient(app), SessionLocal


def test_ingest_accepts_valid_events() -> None:
    global CURRENT_TOKEN
    client, SessionLocal = _make_client()
    client_id = str(uuid4())
    CURRENT_TOKEN = _token_for_client(client_id)

    response = client.post(
        "/api/v1/marketplace/client/events",
        json={
            "events": [
                {
                    "event_type": "marketplace.offer_viewed",
                    "entity_type": "OFFER",
                    "entity_id": str(uuid4()),
                    "session_id": "session-1",
                    "source": "client_portal",
                    "page": "/marketplace/products/123",
                    "payload": {"q": "масло"},
                    "client_ts": datetime.now(timezone.utc).isoformat(),
                }
            ]
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["accepted"] == 1
    assert payload["rejected"] == 0

    with SessionLocal() as db:
        assert db.query(MarketplaceClientEvent).count() == 1

    client.close()


def test_ingest_rejects_unknown_event_type() -> None:
    global CURRENT_TOKEN
    client, _ = _make_client()
    CURRENT_TOKEN = _token_for_client(str(uuid4()))

    response = client.post(
        "/api/v1/marketplace/client/events",
        json={
            "events": [
                {
                    "event_type": "marketplace.unknown_event",
                    "entity_type": "NONE",
                    "source": "client_portal",
                }
            ]
        },
    )
    assert response.status_code == 400
    client.close()


def test_query_returns_events_by_date_range() -> None:
    global CURRENT_TOKEN
    client, SessionLocal = _make_client()
    client_id = str(uuid4())
    CURRENT_TOKEN = _token_for_client(client_id)

    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        _create_event(
            db,
            client_id=client_id,
            event_type=MarketplaceClientEventType.OFFER_VIEWED,
            entity_type=MarketplaceClientEntityType.OFFER,
            entity_id=str(uuid4()),
            ts=now - timedelta(days=10),
        )
        _create_event(
            db,
            client_id=client_id,
            event_type=MarketplaceClientEventType.ORDER_CREATED,
            entity_type=MarketplaceClientEntityType.ORDER,
            entity_id=str(uuid4()),
            ts=now - timedelta(days=1),
        )

    response = client.get(
        "/api/v1/marketplace/client/events",
        params={
            "date_from": (now - timedelta(days=2)).isoformat(),
            "date_to": now.isoformat(),
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["event_type"] == "marketplace.order_created"
    client.close()


def test_query_filters_by_event_type() -> None:
    global CURRENT_TOKEN
    client, SessionLocal = _make_client()
    client_id = str(uuid4())
    CURRENT_TOKEN = _token_for_client(client_id)

    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        _create_event(
            db,
            client_id=client_id,
            event_type=MarketplaceClientEventType.OFFER_VIEWED,
            entity_type=MarketplaceClientEntityType.OFFER,
            entity_id=str(uuid4()),
            ts=now,
        )
        _create_event(
            db,
            client_id=client_id,
            event_type=MarketplaceClientEventType.ORDER_CREATED,
            entity_type=MarketplaceClientEntityType.ORDER,
            entity_id=str(uuid4()),
            ts=now,
        )

    response = client.get(
        "/api/v1/marketplace/client/events",
        params={"event_type": "marketplace.offer_viewed"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["event_type"] == "marketplace.offer_viewed"
    client.close()
