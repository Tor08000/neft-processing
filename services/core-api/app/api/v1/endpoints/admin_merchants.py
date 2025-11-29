from __future__ import annotations

from typing import List, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.merchant import Merchant
from app.models.terminal import Terminal
from app.schemas.admin_merchants import (
    MerchantBase,
    MerchantCreate,
    MerchantListResponse,
    MerchantRead,
    MerchantUpdate,
    TerminalBase,
    TerminalCreate,
    TerminalListResponse,
    TerminalRead,
    TerminalUpdate,
)
from app.security.admin_auth import require_admin

router = APIRouter(
    prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(require_admin)]
)

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


MERCHANT_ORDERING = {
    "id_asc": Merchant.id.asc(),
    "id_desc": Merchant.id.desc(),
    "name_asc": Merchant.name.asc(),
    "name_desc": Merchant.name.desc(),
}


TERMINAL_ORDERING = {
    "id_asc": Terminal.id.asc(),
    "id_desc": Terminal.id.desc(),
    "status_asc": Terminal.status.asc(),
    "status_desc": Terminal.status.desc(),
}


def _get_merchant_or_404(db: Session, merchant_id: str) -> Merchant:
    merchant = db.query(Merchant).filter(Merchant.id == merchant_id).first()
    if not merchant:
        raise HTTPException(status_code=404, detail="merchant not found")
    return merchant


def _get_terminal_or_404(db: Session, terminal_id: str) -> Terminal:
    terminal = db.query(Terminal).filter(Terminal.id == terminal_id).first()
    if not terminal:
        raise HTTPException(status_code=404, detail="terminal not found")
    return terminal


@router.get("/merchants", response_model=MerchantListResponse)
def list_merchants(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    status: str | None = None,
    name: str | None = None,
    order_by: Literal["id_asc", "id_desc", "name_asc", "name_desc"] = "id_desc",
    db: Session = Depends(get_db),
) -> MerchantListResponse:
    query = db.query(Merchant)

    if status:
        query = query.filter(Merchant.status == status)
    if name:
        query = query.filter(Merchant.name.ilike(f"%{name}%"))

    total = query.count()
    order_expr = MERCHANT_ORDERING.get(order_by, MERCHANT_ORDERING["id_desc"])
    items: List[Merchant] = (
        query.order_by(order_expr).offset(offset).limit(limit).all()
    )

    serialized = [
        MerchantRead(id=item.id, name=item.name, status=item.status) for item in items
    ]

    return MerchantListResponse(
        items=serialized,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/merchants/{merchant_id}", response_model=MerchantRead)
def get_merchant(merchant_id: str, db: Session = Depends(get_db)) -> Merchant:
    return _get_merchant_or_404(db, merchant_id)


@router.post(
    "/merchants",
    response_model=MerchantRead,
    status_code=status.HTTP_201_CREATED,
)
def create_merchant(body: MerchantCreate, db: Session = Depends(get_db)) -> Merchant:
    existing = db.query(Merchant).filter(Merchant.id == body.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="merchant already exists")

    merchant = Merchant(**body.dict())
    db.add(merchant)
    db.commit()
    db.refresh(merchant)
    return merchant


@router.put("/merchants/{merchant_id}", response_model=MerchantRead)
def update_merchant(
    merchant_id: str,
    body: MerchantBase,
    db: Session = Depends(get_db),
) -> Merchant:
    merchant = _get_merchant_or_404(db, merchant_id)

    merchant.name = body.name
    merchant.status = body.status

    db.commit()
    db.refresh(merchant)
    return merchant


@router.patch("/merchants/{merchant_id}", response_model=MerchantRead)
def patch_merchant(
    merchant_id: str,
    body: MerchantUpdate,
    db: Session = Depends(get_db),
) -> Merchant:
    merchant = _get_merchant_or_404(db, merchant_id)

    data = body.dict(exclude_unset=True)
    for field, value in data.items():
        setattr(merchant, field, value)

    db.commit()
    db.refresh(merchant)
    return merchant


@router.delete("/merchants/{merchant_id}", response_model=MerchantRead)
def delete_merchant(
    merchant_id: str,
    force: bool = Query(False, description="Hard delete when true"),
    db: Session = Depends(get_db),
) -> Merchant:
    merchant = _get_merchant_or_404(db, merchant_id)

    if force:
        db.delete(merchant)
        db.commit()
        return merchant

    merchant.status = "INACTIVE"
    db.commit()
    db.refresh(merchant)
    return merchant


@router.get("/terminals", response_model=TerminalListResponse)
def list_terminals(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    merchant_id: str | None = None,
    status: str | None = None,
    location: str | None = None,
    order_by: Literal["id_asc", "id_desc", "status_asc", "status_desc"] = "id_desc",
    db: Session = Depends(get_db),
) -> TerminalListResponse:
    query = db.query(Terminal)

    if merchant_id:
        query = query.filter(Terminal.merchant_id == merchant_id)
    if status:
        query = query.filter(Terminal.status == status)
    if location:
        query = query.filter(Terminal.location.ilike(f"%{location}%"))

    total = query.count()
    order_expr = TERMINAL_ORDERING.get(order_by, TERMINAL_ORDERING["id_desc"])
    items: List[Terminal] = (
        query.order_by(order_expr).offset(offset).limit(limit).all()
    )

    serialized = [
        TerminalRead(
            id=item.id,
            merchant_id=item.merchant_id,
            status=item.status,
            location=item.location,
        )
        for item in items
    ]

    return TerminalListResponse(
        items=serialized,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/terminals/{terminal_id}", response_model=TerminalRead)
def get_terminal(terminal_id: str, db: Session = Depends(get_db)) -> Terminal:
    return _get_terminal_or_404(db, terminal_id)


@router.post(
    "/terminals",
    response_model=TerminalRead,
    status_code=status.HTTP_201_CREATED,
)
def create_terminal(body: TerminalCreate, db: Session = Depends(get_db)) -> Terminal:
    _get_merchant_or_404(db, body.merchant_id)

    existing = db.query(Terminal).filter(Terminal.id == body.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="terminal already exists")

    terminal = Terminal(**body.dict())
    db.add(terminal)
    db.commit()
    db.refresh(terminal)
    return terminal


@router.put("/terminals/{terminal_id}", response_model=TerminalRead)
def update_terminal(
    terminal_id: str,
    body: TerminalBase,
    db: Session = Depends(get_db),
) -> Terminal:
    terminal = _get_terminal_or_404(db, terminal_id)

    if body.merchant_id != terminal.merchant_id:
        _get_merchant_or_404(db, body.merchant_id)

    terminal.merchant_id = body.merchant_id
    terminal.status = body.status
    terminal.location = body.location

    db.commit()
    db.refresh(terminal)
    return terminal


@router.patch("/terminals/{terminal_id}", response_model=TerminalRead)
def patch_terminal(
    terminal_id: str,
    body: TerminalUpdate,
    db: Session = Depends(get_db),
) -> Terminal:
    terminal = _get_terminal_or_404(db, terminal_id)

    data = body.dict(exclude_unset=True)
    if "merchant_id" in data and data["merchant_id"] != terminal.merchant_id:
        _get_merchant_or_404(db, data["merchant_id"])

    for field, value in data.items():
        setattr(terminal, field, value)

    db.commit()
    db.refresh(terminal)
    return terminal


@router.delete("/terminals/{terminal_id}", response_model=TerminalRead)
def delete_terminal(
    terminal_id: str,
    force: bool = Query(False, description="Hard delete when true"),
    db: Session = Depends(get_db),
) -> Terminal:
    terminal = _get_terminal_or_404(db, terminal_id)

    if force:
        db.delete(terminal)
        db.commit()
        return terminal

    terminal.status = "INACTIVE"
    db.commit()
    db.refresh(terminal)
    return terminal
