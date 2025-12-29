from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.admin.what_if import WhatIfEvaluateRequest, WhatIfResponse
from app.services.what_if import evaluate_what_if
from app.services.what_if.inputs import WhatIfSubject

router = APIRouter(prefix="/what-if", tags=["admin", "what-if"])


@router.post("/evaluate", response_model=WhatIfResponse)
def evaluate(
    payload: WhatIfEvaluateRequest,
    db: Session = Depends(get_db),
) -> WhatIfResponse:
    try:
        result = evaluate_what_if(
            db,
            subject=WhatIfSubject(type=payload.subject.type, id=payload.subject.id),
            max_candidates=payload.max_candidates,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WhatIfResponse.model_validate(result)


__all__ = ["router"]
