# в начале файла
from sqlalchemy.orm import Session
from fastapi import Depends

from app.deps.db import get_db
from app.crud.operations import create_from_dict

# ...

@router.post("/processing/terminal-auth", response_model=OperationRead)
def terminal_auth(
    payload: AuthRequest,
    db: Session = Depends(get_db),
):
    result = services.process_terminal_auth(payload)

    # <-- ВАЖНО: логируем операцию в БД
    try:
        create_from_dict(db, result.dict())
    except Exception:
        # Логирование можно сделать через твой стандартный логгер,
        # но ответ клиенту не ломаем.
        pass

    return result


@router.post("/transactions/{auth_id}/capture", response_model=OperationRead)
def capture(
    auth_id: UUID,
    payload: CaptureRequest,
    db: Session = Depends(get_db),
):
    result = services.process_capture(auth_id=auth_id, payload=payload)
    try:
        create_from_dict(db, result.dict())
    except Exception:
        pass
    return result


@router.post("/transactions/{capture_id}/refund", response_model=OperationRead)
def refund(
    capture_id: UUID,
    payload: RefundRequest,
    db: Session = Depends(get_db),
):
    result = services.process_refund(capture_id=capture_id, payload=payload)
    try:
        create_from_dict(db, result.dict())
    except Exception:
        pass
    return result


@router.post("/transactions/{op_id}/reversal", response_model=OperationRead)
def reversal(
    op_id: UUID,
    payload: ReversalRequest,
    db: Session = Depends(get_db),
):
    result = services.process_reversal(op_id=op_id, payload=payload)
    try:
        create_from_dict(db, result.dict())
    except Exception:
        pass
    return result
