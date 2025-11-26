from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.merchant import Merchant
from app.models.terminal import Terminal
from app.schemas.terminals import (
    TerminalCreate,
    TerminalSchema,
    TerminalUpdate,
    TerminalsPage,
)

router = APIRouter(prefix="/terminals", tags=["terminals"])


@router.get("", response_model=TerminalsPage)
def list_terminals(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> TerminalsPage:
    query = db.query(Terminal)
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return TerminalsPage(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=TerminalSchema)
def create_terminal(
    payload: TerminalCreate = Body(...), db: Session = Depends(get_db)
) -> TerminalSchema:
    merchant = db.query(Merchant).filter(Merchant.id == payload.merchant_id).first()
    if not merchant:
        raise HTTPException(status_code=400, detail="merchant not found")

    terminal = Terminal(
        id=payload.id,
        merchant_id=payload.merchant_id,
        status=payload.status,
        location=payload.location,
    )
    db.add(terminal)
    db.commit()
    db.refresh(terminal)
    return terminal


@router.get("/{terminal_id}", response_model=TerminalSchema)
def get_terminal(terminal_id: str, db: Session = Depends(get_db)) -> TerminalSchema:
    terminal = db.query(Terminal).filter(Terminal.id == terminal_id).first()
    if not terminal:
        raise HTTPException(status_code=404, detail="terminal not found")
    return terminal


@router.patch("/{terminal_id}", response_model=TerminalSchema)
def update_terminal(
    terminal_id: str, payload: TerminalUpdate = Body(...), db: Session = Depends(get_db)
) -> TerminalSchema:
    terminal = db.query(Terminal).filter(Terminal.id == terminal_id).first()
    if not terminal:
        raise HTTPException(status_code=404, detail="terminal not found")

    if payload.merchant_id is not None:
        merchant = db.query(Merchant).filter(Merchant.id == payload.merchant_id).first()
        if not merchant:
            raise HTTPException(status_code=400, detail="merchant not found")
        terminal.merchant_id = payload.merchant_id

    if payload.status is not None:
        terminal.status = payload.status
    if payload.location is not None:
        terminal.location = payload.location

    db.commit()
    db.refresh(terminal)
    return terminal


@router.delete("/{terminal_id}", response_model=TerminalSchema)
def delete_terminal(terminal_id: str, db: Session = Depends(get_db)) -> TerminalSchema:
    terminal = db.query(Terminal).filter(Terminal.id == terminal_id).first()
    if not terminal:
        raise HTTPException(status_code=404, detail="terminal not found")

    terminal.status = "DELETED"
    db.commit()
    db.refresh(terminal)
    return terminal
