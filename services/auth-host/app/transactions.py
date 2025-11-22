import json
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Request, HTTPException
from .validators import ensure_card_can_spend
from app.db import get_conn
from app.schemas import AuthorizeRequest, AuthorizeResponse, CaptureRequest, ReverseRequest, TxnStatus
from app.idempotency import make_idempotency_key, get_idempotency_key

router = APIRouter(prefix="/v1/tx", tags=["tx"])

HOLD_TTL_MIN = 30

@router.post("/authorize", response_model=AuthorizeResponse)
async def authorize(
    req: AuthorizeRequest,
    request: Request,
    x_idemp: str | None = Depends(get_idempotency_key),
):
    payload_bytes = await request.body()
    idemp_key = make_idempotency_key("POST", "/v1/tx/authorize", payload_bytes, x_idemp)

    async with get_conn() as (conn, cur):
        await conn.execute("BEGIN")
        # идемпотентность: если уже был такой запрос
        await cur.execute(
            "SELECT id, status FROM transactions WHERE idempotency_key=%s",
            (idemp_key,)
        )
        row = await cur.fetchone()
        if row:
            # возвращаем такой же ответ
            await cur.execute("SELECT id, status FROM holds WHERE trans_id=%s", (row["id"],))
            hold = await cur.fetchone()
            return AuthorizeResponse(
                approved=(row["status"] == "approved"),
                trans_id=row["id"],
                hold_id=(hold["id"] if hold else None),
                reason=(None if row["status"] == "approved" else "duplicate")
            )

        # 1) находим карту
        await cur.execute("SELECT id, client_id, status, limit_day, spent_day FROM cards WHERE token=%s FOR UPDATE", (req.card_token,))
        card = await cur.fetchone()
        if not card or card["status"] != "active":
            await conn.rollback()
            return AuthorizeResponse(approved=False, reason="card_not_active")

        # 2) бизнес-проверки лимитов
        ok, reason = await ensure_card_can_spend(cur, card, req.amount)
        if not ok:
            await conn.rollback()
            return AuthorizeResponse(approved=False, reason=reason)

        # 3) создаём транзакцию и холд
        await cur.execute("""
            INSERT INTO transactions (ext_id, idempotency_key, type, status, client_id, card_id, amount, currency, product_code, meta)
            VALUES (%s,%s,'authorize','approved',%s,%s,%s,%s,%s,'{}'::jsonb)
            RETURNING id
        """, (req.ext_id, idemp_key, card["client_id"], card["id"], req.amount, req.currency, req.product_code))
        tr = await cur.fetchone()

        expires = datetime.now(timezone.utc) + timedelta(minutes=HOLD_TTL_MIN)
        await cur.execute("""
            INSERT INTO holds (trans_id, card_id, amount, currency, status, expires_at)
            VALUES (%s,%s,%s,%s,'active',%s)
            RETURNING id
        """, (tr["id"], card["id"], req.amount, req.currency, expires))
        hold = await cur.fetchone()

        # 4) обновляем дневной расход
        await cur.execute(
            "UPDATE cards SET spent_day = spent_day + %s WHERE id = %s",
            (req.amount, card["id"])
        )
        await conn.commit()

        return AuthorizeResponse(approved=True, trans_id=tr["id"], hold_id=hold["id"])

@router.post("/capture", response_model=TxnStatus)
async def capture(req: CaptureRequest):
    async with get_conn() as (conn, cur):
        await conn.execute("BEGIN")
        await cur.execute("SELECT t.id, t.status, h.id AS hold_id, h.amount, h.status AS hold_status FROM transactions t JOIN holds h ON h.trans_id=t.id WHERE t.id=%s FOR UPDATE", (req.trans_id,))
        row = await cur.fetchone()
        if not row:
            await conn.rollback()
            raise HTTPException(404, "transaction_not_found")
        if row["hold_status"] != "active":
            await conn.rollback()
            raise HTTPException(409, "hold_not_active")

        capture_amount = float(req.amount or row["amount"])

        # помечаем холд как captured и создаём capture-транзакцию
        await cur.execute("UPDATE holds SET status='captured' WHERE id=%s", (row["hold_id"],))
        await cur.execute("""
            INSERT INTO transactions (type, status, amount, currency, client_id, card_id, meta)
            SELECT 'capture','captured',%s,'RUB',t.client_id,t.card_id,'{}'::jsonb
            FROM transactions t WHERE t.id=%s
            RETURNING id, status, type, amount, currency, meta
        """, (capture_amount, req.trans_id))
        cap = await cur.fetchone()
        await conn.commit()
        return TxnStatus(**cap)

@router.post("/reverse", response_model=TxnStatus)
async def reverse(req: ReverseRequest):
    async with get_conn() as (conn, cur):
        await conn.execute("BEGIN")
        await cur.execute("SELECT t.id, t.client_id, t.card_id, t.amount, t.currency, h.id AS hold_id, h.status, h.amount AS hold_amount FROM transactions t JOIN holds h ON h.trans_id=t.id WHERE t.id=%s FOR UPDATE", (req.trans_id,))
        row = await cur.fetchone()
        if not row:
            await conn.rollback()
            raise HTTPException(404, "transaction_not_found")
        if row["status"] not in ("active","approved"):
            # если уже был capture — нужна отдельная refund-логика
            await conn.rollback()
            raise HTTPException(409, "transaction_cannot_reverse")

        # снимаем холд и откатываем spent_day
        await cur.execute("UPDATE holds SET status='reversed' WHERE id=%s AND status='active'", (row["hold_id"],))
        await cur.execute("UPDATE cards SET spent_day = GREATEST(spent_day - %s, 0) WHERE id=%s", (row["hold_amount"], row["card_id"]))

        # создаём запись reverse
        await cur.execute("""
            INSERT INTO transactions (type, status, amount, currency, client_id, card_id, meta)
            VALUES ('reverse','reversed',%s,%s,%s,%s,'{}'::jsonb)
            RETURNING id, status, type, amount, currency, meta
        """, (row["amount"], row["currency"], row["client_id"], row["card_id"]))
        rev = await cur.fetchone()
        await conn.commit()
        return TxnStatus(**rev)
