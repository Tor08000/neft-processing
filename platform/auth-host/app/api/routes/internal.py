from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.db import get_conn

router = APIRouter(prefix="/internal", tags=["internal"])


@router.get("/users/lookup")
async def lookup_user(email: str = Query(..., min_length=3)) -> dict[str, str]:
    normalized_email = email.strip().lower()
    if not normalized_email:
        raise HTTPException(status_code=400, detail="email_required")

    async with get_conn() as (_conn, cur):
        await cur.execute(
            "SELECT id::text FROM users WHERE lower(email) = %s LIMIT 1",
            (normalized_email,),
        )
        row = await cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="user_not_found")

    return {"user_id": str(row["id"])}
