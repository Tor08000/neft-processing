from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.card import Card
from app.models.client_portal import CardLimit, LimitTemplate


class CardsRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_cards(self, client_id: str) -> list[Card]:
        return self.db.query(Card).filter(Card.client_id == client_id).order_by(Card.created_at.desc()).all()

    def list_limits(self, client_id: str) -> list[CardLimit]:
        return self.db.query(CardLimit).filter(CardLimit.client_id == client_id).all()

    def list_templates(self, client_id: str) -> list[LimitTemplate]:
        return (
            self.db.query(LimitTemplate)
            .filter(LimitTemplate.client_id == client_id)
            .order_by(LimitTemplate.created_at.desc())
            .all()
        )

    def get_card(self, client_id: str, card_id: str) -> Card | None:
        return self.db.query(Card).filter(Card.client_id == client_id, Card.id == card_id).one_or_none()

    def get_template(self, client_id: str, template_id: str) -> LimitTemplate | None:
        return self.db.query(LimitTemplate).filter(LimitTemplate.client_id == client_id, LimitTemplate.id == template_id).one_or_none()

    def get_default_template(self, client_id: str) -> LimitTemplate | None:
        return (
            self.db.query(LimitTemplate)
            .filter(LimitTemplate.client_id == client_id, LimitTemplate.is_default.is_(True))
            .order_by(LimitTemplate.created_at.desc())
            .first()
        )

    def create_card(self, client_id: str, label: str | None) -> Card:
        now = datetime.now(timezone.utc)
        card = Card(
            id=f"card-{uuid4()}",
            client_id=client_id,
            status="ISSUED",
            pan_masked=label,
            issued_at=now,
        )
        self.db.add(card)
        self.db.flush()
        return card

    def replace_limits(self, client_id: str, card_id: str, items: list[dict]) -> list[CardLimit]:
        self.db.query(CardLimit).filter(CardLimit.client_id == client_id, CardLimit.card_id == card_id).delete()
        limits: list[CardLimit] = []
        for item in items:
            limit = CardLimit(
                client_id=client_id,
                card_id=card_id,
                limit_type=item["limit_type"],
                amount=item["amount"],
                currency=item.get("currency") or "RUB",
                active=item.get("active", True),
            )
            self.db.add(limit)
            limits.append(limit)
        self.db.flush()
        return limits

    def commit(self) -> None:
        self.db.commit()
