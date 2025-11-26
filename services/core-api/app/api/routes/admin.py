from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.limits import CardGroup, CardGroupMembership, ClientGroup, ClientGroupMembership
from app.models.limit_rule import LimitRule
from app.schemas.admin import (
    CardGroupCreate,
    CardGroupResponse,
    CardGroupUpdate,
    ClientGroupCreate,
    ClientGroupResponse,
    ClientGroupUpdate,
    LimitRuleCreate,
    LimitRuleResponse,
    LimitRuleUpdate,
    MembershipRequest,
)


router = APIRouter(prefix="/admin", tags=["admin"])


def _get_client_group_or_404(db: Session, group_id: int) -> ClientGroup:
    group = db.get(ClientGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="client group not found")
    return group


def _get_card_group_or_404(db: Session, group_id: int) -> CardGroup:
    group = db.get(CardGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="card group not found")
    return group


def _get_limit_rule_or_404(db: Session, rule_id: int) -> LimitRule:
    rule = db.get(LimitRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="limit rule not found")
    return rule


def _serialize_client_group(group: ClientGroup) -> ClientGroupResponse:
    return ClientGroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        members=[member.client_id for member in group.memberships],
    )


def _serialize_card_group(group: CardGroup) -> CardGroupResponse:
    return CardGroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        members=[member.card_id for member in group.memberships],
    )


def _serialize_limit_rule(rule: LimitRule) -> LimitRuleResponse:
    return LimitRuleResponse(
        id=rule.id,
        name=rule.name,
        priority=rule.priority,
        daily_limit=rule.daily_limit,
        limit_per_tx=rule.limit_per_tx,
        currency=rule.currency,
        client_group_id=rule.client_group_id,
        card_group_id=rule.card_group_id,
    )


@router.get("/client-groups", response_model=List[ClientGroupResponse])
def list_client_groups(db: Session = Depends(get_db)) -> List[ClientGroupResponse]:
    groups = db.query(ClientGroup).order_by(ClientGroup.id.asc()).all()
    return [_serialize_client_group(group) for group in groups]


@router.post("/client-groups", response_model=ClientGroupResponse)
def create_client_group(
    payload: ClientGroupCreate, db: Session = Depends(get_db)
) -> ClientGroupResponse:
    exists = db.query(ClientGroup).filter(ClientGroup.name == payload.name).first()
    if exists:
        raise HTTPException(status_code=400, detail="client group with this name already exists")

    group = ClientGroup(name=payload.name, description=payload.description)
    db.add(group)
    db.commit()
    db.refresh(group)
    return _serialize_client_group(group)


@router.get("/client-groups/{group_id}", response_model=ClientGroupResponse)
def get_client_group(group_id: int, db: Session = Depends(get_db)) -> ClientGroupResponse:
    group = _get_client_group_or_404(db, group_id)
    return _serialize_client_group(group)


@router.put("/client-groups/{group_id}", response_model=ClientGroupResponse)
def update_client_group(
    group_id: int, payload: ClientGroupUpdate, db: Session = Depends(get_db)
) -> ClientGroupResponse:
    group = _get_client_group_or_404(db, group_id)

    if payload.name:
        name_exists = (
            db.query(ClientGroup)
            .filter(ClientGroup.name == payload.name, ClientGroup.id != group.id)
            .first()
        )
        if name_exists:
            raise HTTPException(status_code=400, detail="client group with this name already exists")
        group.name = payload.name
    if payload.description is not None:
        group.description = payload.description

    db.commit()
    db.refresh(group)
    return _serialize_client_group(group)


@router.delete("/client-groups/{group_id}")
def delete_client_group(group_id: int, db: Session = Depends(get_db)) -> None:
    group = _get_client_group_or_404(db, group_id)
    db.delete(group)
    db.commit()


@router.post("/client-groups/{group_id}/members", response_model=ClientGroupResponse)
def add_client_to_group(
    group_id: int, payload: MembershipRequest, db: Session = Depends(get_db)
) -> ClientGroupResponse:
    group = _get_client_group_or_404(db, group_id)
    membership = (
        db.query(ClientGroupMembership)
        .filter(
            ClientGroupMembership.group_id == group_id,
            ClientGroupMembership.client_id == payload.member_id,
        )
        .first()
    )
    if not membership:
        membership = ClientGroupMembership(group_id=group_id, client_id=payload.member_id)
        db.add(membership)
        db.commit()
    db.refresh(group)
    return _serialize_client_group(group)


@router.delete("/client-groups/{group_id}/members/{client_id}", response_model=ClientGroupResponse)
def remove_client_from_group(
    group_id: int, client_id: str, db: Session = Depends(get_db)
) -> ClientGroupResponse:
    group = _get_client_group_or_404(db, group_id)
    membership = (
        db.query(ClientGroupMembership)
        .filter(
            ClientGroupMembership.group_id == group_id,
            ClientGroupMembership.client_id == client_id,
        )
        .first()
    )
    if membership:
        db.delete(membership)
        db.commit()
    db.refresh(group)
    return _serialize_client_group(group)


@router.get("/card-groups", response_model=List[CardGroupResponse])
def list_card_groups(db: Session = Depends(get_db)) -> List[CardGroupResponse]:
    groups = db.query(CardGroup).order_by(CardGroup.id.asc()).all()
    return [_serialize_card_group(group) for group in groups]


@router.post("/card-groups", response_model=CardGroupResponse)
def create_card_group(
    payload: CardGroupCreate, db: Session = Depends(get_db)
) -> CardGroupResponse:
    exists = db.query(CardGroup).filter(CardGroup.name == payload.name).first()
    if exists:
        raise HTTPException(status_code=400, detail="card group with this name already exists")

    group = CardGroup(name=payload.name, description=payload.description)
    db.add(group)
    db.commit()
    db.refresh(group)
    return _serialize_card_group(group)


@router.get("/card-groups/{group_id}", response_model=CardGroupResponse)
def get_card_group(group_id: int, db: Session = Depends(get_db)) -> CardGroupResponse:
    group = _get_card_group_or_404(db, group_id)
    return _serialize_card_group(group)


@router.put("/card-groups/{group_id}", response_model=CardGroupResponse)
def update_card_group(
    group_id: int, payload: CardGroupUpdate, db: Session = Depends(get_db)
) -> CardGroupResponse:
    group = _get_card_group_or_404(db, group_id)

    if payload.name:
        name_exists = (
            db.query(CardGroup)
            .filter(CardGroup.name == payload.name, CardGroup.id != group.id)
            .first()
        )
        if name_exists:
            raise HTTPException(status_code=400, detail="card group with this name already exists")
        group.name = payload.name
    if payload.description is not None:
        group.description = payload.description

    db.commit()
    db.refresh(group)
    return _serialize_card_group(group)


@router.delete("/card-groups/{group_id}")
def delete_card_group(group_id: int, db: Session = Depends(get_db)) -> None:
    group = _get_card_group_or_404(db, group_id)
    db.delete(group)
    db.commit()


@router.post("/card-groups/{group_id}/members", response_model=CardGroupResponse)
def add_card_to_group(
    group_id: int, payload: MembershipRequest, db: Session = Depends(get_db)
) -> CardGroupResponse:
    group = _get_card_group_or_404(db, group_id)
    membership = (
        db.query(CardGroupMembership)
        .filter(
            CardGroupMembership.group_id == group_id,
            CardGroupMembership.card_id == payload.member_id,
        )
        .first()
    )
    if not membership:
        membership = CardGroupMembership(group_id=group_id, card_id=payload.member_id)
        db.add(membership)
        db.commit()
    db.refresh(group)
    return _serialize_card_group(group)


@router.delete("/card-groups/{group_id}/members/{card_id}", response_model=CardGroupResponse)
def remove_card_from_group(
    group_id: int, card_id: str, db: Session = Depends(get_db)
) -> CardGroupResponse:
    group = _get_card_group_or_404(db, group_id)
    membership = (
        db.query(CardGroupMembership)
        .filter(
            CardGroupMembership.group_id == group_id,
            CardGroupMembership.card_id == card_id,
        )
        .first()
    )
    if membership:
        db.delete(membership)
        db.commit()
    db.refresh(group)
    return _serialize_card_group(group)


def _validate_group_reference(db: Session, group_id: int, model: type) -> None:
    if group_id is None:
        return
    exists = db.get(model, group_id)
    if not exists:
        raise HTTPException(status_code=400, detail=f"{model.__name__} does not exist")


@router.get("/limit-rules", response_model=List[LimitRuleResponse])
def list_limit_rules(db: Session = Depends(get_db)) -> List[LimitRuleResponse]:
    rules = (
        db.query(LimitRule)
        .order_by(LimitRule.priority.desc(), LimitRule.id.asc())
        .all()
    )
    return [_serialize_limit_rule(rule) for rule in rules]


@router.post("/limit-rules", response_model=LimitRuleResponse)
def create_limit_rule(
    payload: LimitRuleCreate, db: Session = Depends(get_db)
) -> LimitRuleResponse:
    _validate_group_reference(db, payload.client_group_id, ClientGroup)
    _validate_group_reference(db, payload.card_group_id, CardGroup)

    rule = LimitRule(
        name=payload.name,
        priority=payload.priority,
        daily_limit=payload.daily_limit,
        limit_per_tx=payload.limit_per_tx,
        currency=payload.currency,
        client_group_id=payload.client_group_id,
        card_group_id=payload.card_group_id,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _serialize_limit_rule(rule)


@router.get("/limit-rules/{rule_id}", response_model=LimitRuleResponse)
def get_limit_rule(rule_id: int, db: Session = Depends(get_db)) -> LimitRuleResponse:
    rule = _get_limit_rule_or_404(db, rule_id)
    return _serialize_limit_rule(rule)


@router.put("/limit-rules/{rule_id}", response_model=LimitRuleResponse)
def update_limit_rule(
    rule_id: int, payload: LimitRuleUpdate, db: Session = Depends(get_db)
) -> LimitRuleResponse:
    rule = _get_limit_rule_or_404(db, rule_id)

    if payload.client_group_id is not None:
        _validate_group_reference(db, payload.client_group_id, ClientGroup)
        rule.client_group_id = payload.client_group_id
    if payload.card_group_id is not None:
        _validate_group_reference(db, payload.card_group_id, CardGroup)
        rule.card_group_id = payload.card_group_id
    if payload.name:
        rule.name = payload.name
    if payload.priority is not None:
        rule.priority = payload.priority
    if payload.daily_limit is not None:
        rule.daily_limit = payload.daily_limit
    if payload.limit_per_tx is not None:
        rule.limit_per_tx = payload.limit_per_tx
    if payload.currency:
        rule.currency = payload.currency

    db.commit()
    db.refresh(rule)
    return _serialize_limit_rule(rule)


@router.delete("/limit-rules/{rule_id}")
def delete_limit_rule(rule_id: int, db: Session = Depends(get_db)) -> None:
    rule = _get_limit_rule_or_404(db, rule_id)
    db.delete(rule)
    db.commit()
