from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.groups import (
    CardGroup,
    CardGroupMember,
    ClientGroup,
    ClientGroupMember,
)
from app.models.limit_rule import LimitRule
from app.schemas.admin.groups import (
    CardGroupCreate,
    CardGroupListResponse,
    CardGroupMemberChange,
    CardGroupMemberRead,
    CardGroupRead,
    CardGroupUpdate,
    ClientGroupCreate,
    ClientGroupListResponse,
    ClientGroupMemberChange,
    ClientGroupMemberRead,
    ClientGroupRead,
    ClientGroupUpdate,
)
from app.schemas.admin.limits import (
    LimitRuleCreate,
    LimitRuleListResponse,
    LimitRuleRead,
    LimitRuleUpdate,
)


router = APIRouter(prefix="", tags=["admin"])


def _validate_limits(
    daily_limit: Optional[int], limit_per_tx: Optional[int], max_amount: Optional[int]
) -> None:
    if daily_limit is None and limit_per_tx is None and max_amount is None:
        raise HTTPException(status_code=400, detail="at least one limit must be set")


def _get_limit_rule_or_404(db: Session, rule_id: int) -> LimitRule:
    rule = db.query(LimitRule).filter(LimitRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="limit rule not found")
    return rule


@router.get("/limits/rules", response_model=LimitRuleListResponse)
def list_limit_rules(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    phase: str | None = None,
    client_id: str | None = None,
    card_id: str | None = None,
    merchant_id: str | None = None,
    terminal_id: str | None = None,
    client_group_id: str | None = None,
    card_group_id: str | None = None,
    product_category: str | None = None,
    mcc: str | None = None,
    tx_type: str | None = None,
    active: bool | None = None,
    db: Session = Depends(get_db),
) -> LimitRuleListResponse:
    query = db.query(LimitRule)

    if phase:
        query = query.filter(LimitRule.phase == phase)
    if client_id:
        query = query.filter(LimitRule.client_id == client_id)
    if card_id:
        query = query.filter(LimitRule.card_id == card_id)
    if merchant_id:
        query = query.filter(LimitRule.merchant_id == merchant_id)
    if terminal_id:
        query = query.filter(LimitRule.terminal_id == terminal_id)
    if client_group_id:
        query = query.filter(LimitRule.client_group_id == client_group_id)
    if card_group_id:
        query = query.filter(LimitRule.card_group_id == card_group_id)
    if product_category:
        query = query.filter(LimitRule.product_category == product_category)
    if mcc:
        query = query.filter(LimitRule.mcc == mcc)
    if tx_type:
        query = query.filter(LimitRule.tx_type == tx_type)
    if active is not None:
        query = query.filter(LimitRule.active == active)

    total = query.count()
    items = (
        query.order_by(LimitRule.id.asc()).offset(offset).limit(limit).all()
    )
    return LimitRuleListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/limits/rules/{rule_id}", response_model=LimitRuleRead)
def get_limit_rule(rule_id: int, db: Session = Depends(get_db)) -> LimitRule:
    return _get_limit_rule_or_404(db, rule_id)


@router.post(
    "/limits/rules",
    response_model=LimitRuleRead,
    status_code=status.HTTP_201_CREATED,
)
def create_limit_rule(body: LimitRuleCreate, db: Session = Depends(get_db)) -> LimitRule:
    _validate_limits(body.daily_limit, body.limit_per_tx, body.max_amount)

    rule = LimitRule(**body.dict())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.put("/limits/rules/{rule_id}", response_model=LimitRuleRead)
def update_limit_rule(
    rule_id: int, body: LimitRuleUpdate, db: Session = Depends(get_db)
) -> LimitRule:
    rule = _get_limit_rule_or_404(db, rule_id)

    data = body.dict(exclude_unset=True)
    for field, value in data.items():
        setattr(rule, field, value)

    new_daily = rule.daily_limit
    new_per_tx = rule.limit_per_tx
    _validate_limits(new_daily, new_per_tx, rule.max_amount)

    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/limits/rules/{rule_id}", response_model=LimitRuleRead)
def delete_limit_rule(
    rule_id: int,
    force: bool = Query(False, description="Hard delete when true"),
    db: Session = Depends(get_db),
) -> LimitRule:
    rule = _get_limit_rule_or_404(db, rule_id)

    if force:
        db.delete(rule)
        db.commit()
        return rule

    rule.active = False
    db.commit()
    db.refresh(rule)
    return rule


def _get_client_group_or_404(db: Session, group_id: str) -> ClientGroup:
    group = db.query(ClientGroup).filter(ClientGroup.group_id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="client group not found")
    return group


@router.get("/client-groups", response_model=ClientGroupListResponse)
def list_client_groups(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> ClientGroupListResponse:
    query = db.query(ClientGroup)
    total = query.count()
    items = query.order_by(ClientGroup.id.asc()).offset(offset).limit(limit).all()
    return ClientGroupListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/client-groups/{group_id}", response_model=ClientGroupRead)
def get_client_group(group_id: str, db: Session = Depends(get_db)) -> ClientGroup:
    return _get_client_group_or_404(db, group_id)


@router.post(
    "/client-groups",
    response_model=ClientGroupRead,
    status_code=status.HTTP_201_CREATED,
)
def create_client_group(
    body: ClientGroupCreate, db: Session = Depends(get_db)
) -> ClientGroup:
    existing = db.query(ClientGroup).filter(ClientGroup.group_id == body.group_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="client group already exists")

    group = ClientGroup(**body.dict())
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@router.put("/client-groups/{group_id}", response_model=ClientGroupRead)
def update_client_group(
    group_id: str, body: ClientGroupUpdate, db: Session = Depends(get_db)
) -> ClientGroup:
    group = _get_client_group_or_404(db, group_id)
    data = body.dict(exclude_unset=True)
    for field, value in data.items():
        setattr(group, field, value)
    db.commit()
    db.refresh(group)
    return group


@router.delete(
    "/client-groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_client_group(group_id: str, db: Session = Depends(get_db)) -> None:
    group = _get_client_group_or_404(db, group_id)
    db.delete(group)
    db.commit()


@router.get(
    "/client-groups/{group_id}/members",
    response_model=list[ClientGroupMemberRead],
)
def list_client_group_members(
    group_id: str, db: Session = Depends(get_db)
) -> list[ClientGroupMemberRead]:
    group = _get_client_group_or_404(db, group_id)
    return [
        ClientGroupMemberRead(client_id=member.client_id, created_at=member.created_at)
        for member in group.members
    ]


@router.post(
    "/client-groups/{group_id}/members",
    response_model=ClientGroupMemberRead,
    status_code=status.HTTP_201_CREATED,
)
def add_client_group_member(
    group_id: str, body: ClientGroupMemberChange, db: Session = Depends(get_db)
) -> ClientGroupMemberRead:
    group = _get_client_group_or_404(db, group_id)
    existing = (
        db.query(ClientGroupMember)
        .filter(
            ClientGroupMember.client_group_id == group.id,
            ClientGroupMember.client_id == body.client_id,
        )
        .first()
    )
    if existing:
        return ClientGroupMemberRead(client_id=existing.client_id, created_at=existing.created_at)

    member = ClientGroupMember(client_group_id=group.id, client_id=body.client_id)
    db.add(member)
    db.commit()
    db.refresh(member)
    return ClientGroupMemberRead(client_id=member.client_id, created_at=member.created_at)


@router.delete(
    "/client-groups/{group_id}/members/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def remove_client_group_member(
    group_id: str, client_id: str, db: Session = Depends(get_db)
) -> None:
    group = _get_client_group_or_404(db, group_id)
    db.query(ClientGroupMember).filter(
        ClientGroupMember.client_group_id == group.id,
        ClientGroupMember.client_id == client_id,
    ).delete()
    db.commit()


def _get_card_group_or_404(db: Session, group_id: str) -> CardGroup:
    group = db.query(CardGroup).filter(CardGroup.group_id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="card group not found")
    return group


@router.get("/card-groups", response_model=CardGroupListResponse)
def list_card_groups(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> CardGroupListResponse:
    query = db.query(CardGroup)
    total = query.count()
    items = query.order_by(CardGroup.id.asc()).offset(offset).limit(limit).all()
    return CardGroupListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/card-groups/{group_id}", response_model=CardGroupRead)
def get_card_group(group_id: str, db: Session = Depends(get_db)) -> CardGroup:
    return _get_card_group_or_404(db, group_id)


@router.post(
    "/card-groups",
    response_model=CardGroupRead,
    status_code=status.HTTP_201_CREATED,
)
def create_card_group(body: CardGroupCreate, db: Session = Depends(get_db)) -> CardGroup:
    existing = db.query(CardGroup).filter(CardGroup.group_id == body.group_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="card group already exists")

    group = CardGroup(**body.dict())
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@router.put("/card-groups/{group_id}", response_model=CardGroupRead)
def update_card_group(
    group_id: str, body: CardGroupUpdate, db: Session = Depends(get_db)
) -> CardGroup:
    group = _get_card_group_or_404(db, group_id)
    data = body.dict(exclude_unset=True)
    for field, value in data.items():
        setattr(group, field, value)
    db.commit()
    db.refresh(group)
    return group


@router.delete(
    "/card-groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def delete_card_group(group_id: str, db: Session = Depends(get_db)) -> None:
    group = _get_card_group_or_404(db, group_id)
    db.delete(group)
    db.commit()


@router.get(
    "/card-groups/{group_id}/members",
    response_model=list[CardGroupMemberRead],
)
def list_card_group_members(
    group_id: str, db: Session = Depends(get_db)
) -> list[CardGroupMemberRead]:
    group = _get_card_group_or_404(db, group_id)
    return [
        CardGroupMemberRead(card_id=member.card_id, created_at=member.created_at)
        for member in group.members
    ]


@router.post(
    "/card-groups/{group_id}/members",
    response_model=CardGroupMemberRead,
    status_code=status.HTTP_201_CREATED,
)
def add_card_group_member(
    group_id: str, body: CardGroupMemberChange, db: Session = Depends(get_db)
) -> CardGroupMemberRead:
    group = _get_card_group_or_404(db, group_id)
    existing = (
        db.query(CardGroupMember)
        .filter(
            CardGroupMember.card_group_id == group.id,
            CardGroupMember.card_id == body.card_id,
        )
        .first()
    )
    if existing:
        return CardGroupMemberRead(card_id=existing.card_id, created_at=existing.created_at)

    member = CardGroupMember(card_group_id=group.id, card_id=body.card_id)
    db.add(member)
    db.commit()
    db.refresh(member)
    return CardGroupMemberRead(card_id=member.card_id, created_at=member.created_at)


@router.delete(
    "/card-groups/{group_id}/members/{card_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def remove_card_group_member(
    group_id: str, card_id: str, db: Session = Depends(get_db)
) -> None:
    group = _get_card_group_or_404(db, group_id)
    db.query(CardGroupMember).filter(
        CardGroupMember.card_group_id == group.id,
        CardGroupMember.card_id == card_id,
    ).delete()
    db.commit()
