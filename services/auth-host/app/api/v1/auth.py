from fastapi import APIRouter, Header, HTTPException
import httpx, json
from ...config import CORE_API, AI_URL, TENANT, REDIS_URL, SERVICE_TOKEN
from ...lib.idempotency import idem_lock

router = APIRouter()

def _svc_headers():
    return {"Authorization": f"Bearer {SERVICE_TOKEN}"}

@router.get("/health")
async def health():
    return {"status": "ok"}

@router.post("/authorize")
async def authorize(payload: dict, Idempotency_Key: str | None = Header(default=None)):
    required = ["card_token","azs_id","pos_id","product_id"]
    for k in required:
        if k not in payload: raise HTTPException(400, f"missing:{k}")

    idem = Idempotency_Key or f"{payload.get('card_token')}:{payload.get('azs_id')}:{payload.get('product_id')}:{payload.get('qty')}:{payload.get('amount')}"

    async with idem_lock(REDIS_URL, idem, ttl_sec=60) as ctx:
        if ctx.get("replay"):
            return json.loads(ctx["cached"])

        async with httpx.AsyncClient(timeout=3.0, headers=_svc_headers()) as client:
            # 1) pricing
            pr = await client.post(f"{CORE_API}/v1/auth/internal/pricing/resolve",
                                   params={"azs_id": payload["azs_id"], "product_id": payload["product_id"]})
            if pr.status_code != 200:
                resp = {"approved": False, "code": "PRICE_NOT_FOUND"}
                if ctx.get("redis"): await ctx["redis"].set(ctx["resp_key"], json.dumps(resp), ex=ctx["ttl"])
                return resp
            price = pr.json()["price"]

            # 2) rules
            event = {
                "tenant_id": TENANT,
                "card_token": payload["card_token"],
                "client_id": payload.get("client_id"),
                "azs_id": payload["azs_id"],
                "pos_id": payload["pos_id"],
                "product_id": payload["product_id"],
                "product": payload.get("product_code","AI95"),
                "hour": __import__("datetime").datetime.utcnow().hour,
                "qty": payload.get("qty"),
                "amount": payload.get("amount"),
            }
            rr = await client.post(f"{CORE_API}/v1/auth/internal/rules/evaluate", json=event)
            dec = rr.json().get("decision","ALLOW")
            if dec == "HARD_DECLINE":
                resp = {"approved": False, "code": "LIMIT_RULE"}
                if ctx.get("redis"): await ctx["redis"].set(ctx["resp_key"], json.dumps(resp), ex=ctx["ttl"])
                return resp

            # 3) risk
            rj = (await client.post(f"{AI_URL}/v1/score", json={"event": event})).json()
            if rj.get("decision_hint") == "SOFT_DECLINE":
                resp = {"approved": False, "code": "RISK_SOFT", "risk": rj}
                if ctx.get("redis"): await ctx["redis"].set(ctx["resp_key"], json.dumps(resp), ex=ctx["ttl"])
                return resp

            # 4) persist PRE_AUTH
            trn = {
                "tenant_id": TENANT, "state":"PRE_AUTH",
                "client_id": payload.get("client_id"),
                "wallet_id": payload.get("wallet_id"),
                "card_id": payload.get("card_id"),
                "azs_id": payload["azs_id"], "pos_id": payload["pos_id"],
                "product_id": payload["product_id"],
                "qty": payload.get("qty"), "amount": payload.get("amount"),
                "currency":"RUB",
                "meta": {"price": price, "decision": "APPROVE"}
            }
            await client.post(f"{CORE_API}/v1/transactions", json=trn)

            final = payload.get("amount") or (price * (payload.get("qty") or 0))
            resp = {"approved": True, "price": price, "final_amount": final, "risk": rj}
            if ctx.get("redis"): await ctx["redis"].set(ctx["resp_key"], json.dumps(resp), ex=ctx["ttl"])
            return resp

@router.post("/capture")
async def capture(body: dict):
    txn_id = body.get("txn_id")
    if not txn_id: raise HTTPException(400, "missing:txn_id")
    async with httpx.AsyncClient(timeout=3.0, headers=_svc_headers()) as client:
        await client.patch(f"{CORE_API}/v1/transactions/{txn_id}/capture", json={"amount": body.get("amount")})
    return {"ok": True}

@router.post("/reverse")
async def reverse(body: dict):
    txn_id = body.get("txn_id")
    if not txn_id: raise HTTPException(400, "missing:txn_id")
    async with httpx.AsyncClient(timeout=3.0, headers=_svc_headers()) as client:
        await client.patch(f"{CORE_API}/v1/transactions/{txn_id}/reverse", json={"reason": body.get("reason","")})
    return {"ok": True}
