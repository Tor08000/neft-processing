from __future__ import annotations

from app.domains.cards.models import CardDTO, CardLimitDTO, CardsResponseDTO, CardTemplateSummaryDTO
from app.domains.cards.repo import CardsRepository
from app.domains.cards.schemas import CardCreateInput, LimitUpdate

ALLOWED_LIMIT_TYPES = {"DAILY", "WEEKLY", "MONTHLY", "PER_TX", "FUEL_VOLUME", "FUEL_AMOUNT"}


class CardsDomainError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class CardsService:
    def __init__(self, repo: CardsRepository):
        self.repo = repo

    def list_cards(self, client_id: str) -> CardsResponseDTO:
        cards = self.repo.list_cards(client_id)
        limits = self.repo.list_limits(client_id)
        templates = self.repo.list_templates(client_id)
        limits_by_card: dict[str, list[CardLimitDTO]] = {}
        for item in limits:
            limits_by_card.setdefault(str(item.card_id), []).append(
                CardLimitDTO(
                    limit_type=str(item.limit_type),
                    amount=float(item.amount),
                    currency=str(item.currency),
                    active=bool(getattr(item, "active", True)),
                )
            )
        return CardsResponseDTO(
            items=[
                CardDTO(
                    id=str(card.id),
                    status=str(card.status),
                    masked_pan=card.pan_masked,
                    issued_at=getattr(card, "issued_at", None),
                    limits=limits_by_card.get(str(card.id), []),
                )
                for card in cards
            ],
            templates=[
                CardTemplateSummaryDTO(
                    id=str(item.id),
                    name=str(item.name),
                    is_default=bool(getattr(item, "is_default", False)),
                )
                for item in templates
            ],
        )

    def create_card(self, client_id: str, payload: CardCreateInput) -> CardDTO:
        card = self.repo.create_card(client_id=client_id, label=payload.label)
        template = None
        if payload.template_id:
            template = self.repo.get_template(client_id, payload.template_id)
            if template is None:
                raise CardsDomainError("template_not_found", "Template not found")
        else:
            template = self.repo.get_default_template(client_id)
        template_limits = template.limits if template and isinstance(template.limits, list) else []
        limits_payload = []
        for row in template_limits:
            amount = float(row.get("value", 0))
            if amount <= 0:
                continue
            limits_payload.append(
                {
                    "limit_type": str(row.get("type", "")),
                    "amount": amount,
                    "currency": str(row.get("currency", "RUB")),
                    "active": bool(row.get("active", True)),
                }
            )
        limits = self.repo.replace_limits(client_id=client_id, card_id=str(card.id), items=limits_payload)
        self.repo.commit()
        return CardDTO(
            id=str(card.id),
            status=str(card.status),
            masked_pan=card.pan_masked,
            issued_at=getattr(card, "issued_at", None),
            limits=[
                CardLimitDTO(limit_type=item.limit_type, amount=float(item.amount), currency=item.currency, active=bool(item.active))
                for item in limits
            ],
        )

    def replace_limits(self, client_id: str, card_id: str, limits: list[LimitUpdate]) -> CardDTO:
        card = self.repo.get_card(client_id, card_id)
        if card is None:
            raise CardsDomainError("card_not_found", "Card not found")
        rows = []
        for item in limits:
            if item.limit_type not in ALLOWED_LIMIT_TYPES or item.amount <= 0 or len(item.currency) != 3:
                raise CardsDomainError("invalid_limit", "Invalid limit payload")
            rows.append(
                {
                    "limit_type": item.limit_type,
                    "amount": item.amount,
                    "currency": item.currency.upper(),
                    "active": item.active,
                }
            )
        created = self.repo.replace_limits(client_id=client_id, card_id=card_id, items=rows)
        self.repo.commit()
        return CardDTO(
            id=str(card.id),
            status=str(card.status),
            masked_pan=card.pan_masked,
            issued_at=getattr(card, "issued_at", None),
            limits=[
                CardLimitDTO(limit_type=item.limit_type, amount=float(item.amount), currency=item.currency, active=bool(item.active))
                for item in created
            ],
        )
