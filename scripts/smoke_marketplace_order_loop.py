from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "docs" / "diag" / "marketplace-order-loop-live-smoke-20260425.json"


class SmokeFailure(RuntimeError):
    pass


def env(name: str, default: str) -> str:
    return os.environ.get(name) or default


AUTH_HOST_BASE = env("AUTH_HOST_BASE", "http://localhost:8002").rstrip("/")
CORE_API_BASE = env("CORE_API_BASE", "http://localhost:8001").rstrip("/")
AUTH_BASE = env("AUTH_BASE", "/api/v1/auth")
CORE_BASE = env("CORE_BASE", "/api/core")
LEGACY_API_BASE = env("LEGACY_API_BASE", "/api")
POSTGRES_PASSWORD = env("POSTGRES_PASSWORD", "change-me")

ADMIN_EMAIL = env("ADMIN_EMAIL", "admin@neft.local")
ADMIN_PASSWORD = env("ADMIN_PASSWORD", "Neft123!")
CLIENT_EMAIL = env("CLIENT_EMAIL", "client@neft.local")
CLIENT_PASSWORD = env("CLIENT_PASSWORD", "Client123!")
PARTNER_EMAIL = env("PARTNER_EMAIL", "partner@neft.local")
PARTNER_PASSWORD = env("PARTNER_PASSWORD", "Partner123!")

AUTH_URL = f"{AUTH_HOST_BASE}{AUTH_BASE}"
CORE_ROOT = f"{CORE_API_BASE}{CORE_BASE}"
LEGACY_API_ROOT = f"{CORE_API_BASE}{LEGACY_API_BASE}"


def log(message: str) -> None:
    print(message, flush=True)


def run_command(args: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=ROOT,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        details = (result.stdout or "") + (result.stderr or "")
        raise SmokeFailure(f"command failed: {' '.join(args)}\n{details.strip()}")
    return result


def http_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    body: dict[str, Any] | None = None,
    expected: int | tuple[int, ...] = 200,
) -> tuple[int, Any]:
    expected_codes = (expected,) if isinstance(expected, int) else expected
    payload: bytes | None = None
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = token if token.lower().startswith("bearer ") else f"Bearer {token}"
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=payload, headers=headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            status = response.status
            raw = response.read()
    except HTTPError as exc:
        status = exc.code
        raw = exc.read()
    except URLError as exc:
        raise SmokeFailure(f"{method} {url} failed: {exc}") from exc

    text = raw.decode("utf-8", errors="replace") if raw else ""
    try:
        data: Any = json.loads(text) if text else {}
    except json.JSONDecodeError:
        data = text
    if status not in expected_codes:
        preview = json.dumps(data, ensure_ascii=False) if not isinstance(data, str) else data
        raise SmokeFailure(f"{method} {url} expected {expected_codes}, got {status}: {preview[:2000]}")
    return status, data


def http_status(method: str, url: str, *, token: str | None = None, expected: int = 200) -> int:
    status, _ = http_json(method, url, token=token, expected=expected)
    return status


def wait_for_status(url: str, expected: int, attempts: int = 20, delay: float = 2.0) -> None:
    last: int | str = "no_response"
    for _ in range(attempts):
        try:
            request = Request(url, method="GET")
            with urlopen(request, timeout=10) as response:
                last = response.status
        except HTTPError as exc:
            last = exc.code
        except URLError as exc:
            last = str(exc.reason)
        if last == expected:
            return
        time.sleep(delay)
    raise SmokeFailure(f"{url} did not reach {expected}; last={last}")


def require(condition: bool, message: str, payload: Any | None = None) -> None:
    if condition:
        return
    details = ""
    if payload is not None:
        details = "\n" + json.dumps(payload, ensure_ascii=False, indent=2, default=str)[:3000]
    raise SmokeFailure(message + details)


def login(email: str, password: str, portal: str) -> str:
    _, data = http_json(
        "POST",
        f"{AUTH_URL}/login",
        body={"email": email, "password": password, "portal": portal},
        expected=200,
    )
    token = data.get("access_token") if isinstance(data, dict) else None
    require(bool(token), f"{portal} login missing access_token", data)
    return str(token)


def bootstrap_demo_context() -> None:
    run_command(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "core-api",
            "python",
            "-c",
            (
                "from app.db import get_sessionmaker; "
                "from app.services.bootstrap import ensure_demo_client, ensure_demo_partner, ensure_demo_portal_bindings; "
                "Session=get_sessionmaker(); db=Session(); "
                "ensure_demo_client(db); ensure_demo_partner(db); ensure_demo_portal_bindings(db); db.close()"
            ),
        ]
    )


def psql(sql: str) -> str:
    result = run_command(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "-e",
            f"PGPASSWORD={POSTGRES_PASSWORD}",
            "postgres",
            "psql",
            "-U",
            "neft",
            "-d",
            "neft",
            "-v",
            "ON_ERROR_STOP=1",
            "-t",
            "-A",
        ],
        input_text=sql,
    )
    return result.stdout


def first_error(value: Any) -> str:
    if isinstance(value, dict):
        detail = value.get("detail")
        if isinstance(detail, dict):
            return str(detail.get("error") or detail.get("code") or "")
        return str(value.get("error") or detail or "")
    return str(value or "")


def evidence_doc(extra: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "surface": "marketplace_order_loop",
        "status": "VERIFIED_RUNTIME",
        "command": "cmd /c scripts\\smoke_marketplace_order_loop.cmd",
        "public_api_change": "none; command wrapper now delegates to Python smoke to avoid Windows cmd parser drift",
        "checks": [
            "client browse/offers/create/pay",
            "partner list/confirm/proof/complete",
            "client incidents and consequences",
            "partner settlement pending 409 before admin finalization",
            "admin detail/events/settlement snapshot/consequences",
            "partner settlement finalized 200 after admin override",
            "database order/case/event persistence",
        ],
        **extra,
    }
    EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    evidence: dict[str, Any] = {}
    try:
        log("[0/11] Check docker compose postgres...")
        run_command(["docker", "compose", "ps", "postgres"])

        log("[0.1/11] Check auth + core surfaces...")
        openapi_urls = [
            f"{AUTH_URL}/openapi.json",
            f"{AUTH_HOST_BASE}/openapi.json",
            f"{AUTH_HOST_BASE}/api/auth/openapi.json",
        ]
        auth_ok = False
        for url in openapi_urls:
            try:
                request = Request(url, method="GET")
                with urlopen(request, timeout=10) as response:
                    auth_ok = response.status == 200
                if auth_ok:
                    break
            except (HTTPError, URLError):
                continue
        require(auth_ok, f"auth host is not reachable at {AUTH_URL}")
        wait_for_status(f"{CORE_API_BASE}/health", 200)
        http_json("GET", f"{CORE_API_BASE}/health", expected=200)

        log("[1/11] Login admin, client, and partner...")
        admin_token = login(ADMIN_EMAIL, ADMIN_PASSWORD, "admin")
        client_token = login(CLIENT_EMAIL, CLIENT_PASSWORD, "client")
        partner_token = login(PARTNER_EMAIL, PARTNER_PASSWORD, "partner")

        log("[2/11] Verify auth surfaces...")
        http_status("GET", f"{CORE_ROOT}/admin/auth/verify", token=admin_token, expected=204)
        http_status("GET", f"{CORE_ROOT}/client/auth/verify", token=client_token, expected=204)
        http_status("GET", f"{CORE_ROOT}/partner/auth/verify", token=partner_token, expected=204)

        log("[2.5/11] Ensure demo client and partner bootstrap...")
        bootstrap_demo_context()

        log("[3/11] Resolve client + partner portal context...")
        _, client_portal = http_json("GET", f"{CORE_ROOT}/portal/me", token=client_token, expected=200)
        client_org = client_portal.get("org") or {}
        client_caps = {str(item) for item in (client_portal.get("capabilities") or [])}
        marketplace_module = ((client_portal.get("entitlements_snapshot") or {}).get("modules") or {}).get("MARKETPLACE") or {}
        require(
            bool(client_org.get("id")) and "MARKETPLACE" in client_caps and bool(marketplace_module.get("enabled")),
            "seeded client portal context does not expose MARKETPLACE capability truth",
            client_portal,
        )
        client_id = str(client_org["id"])

        _, partner_portal = http_json("GET", f"{CORE_ROOT}/portal/me", token=partner_token, expected=200)
        partner = partner_portal.get("partner") or {}
        partner_org = partner_portal.get("org") or {}
        partner_id = str(partner.get("partner_id") or partner_org.get("id") or "")
        require(
            partner_portal.get("access_state") == "ACTIVE" and bool(partner_id),
            "seeded partner portal context is not ACTIVE",
            partner_portal,
        )

        run_id = uuid.uuid4().hex[:10]
        product_id = str(uuid.uuid4())
        offer_id = str(uuid.uuid4())
        proof_attachment_id = str(uuid.uuid4())
        category = f"smoke-marketplace-{run_id}"

        log("[4/11] Seed marketplace catalog surface...")
        seed_sql = f"""
SET search_path TO processing_core;
INSERT INTO marketplace_partner_profiles (id, partner_id, company_name, description, verification_status, created_at, updated_at)
VALUES (gen_random_uuid(), '{partner_id}', 'Smoke Marketplace Partner {run_id}', 'Seeded partner profile for marketplace smoke', 'VERIFIED', now(), now())
ON CONFLICT (partner_id) DO UPDATE
SET company_name = EXCLUDED.company_name,
    description = EXCLUDED.description,
    verification_status = 'VERIFIED',
    updated_at = now();
INSERT INTO marketplace_products (
    id, partner_id, type, title, description, category, price_model, price_config,
    status, moderation_status, created_at, updated_at, published_at
)
VALUES (
    '{product_id}', '{partner_id}', 'SERVICE', 'Smoke Marketplace {run_id}',
    'Runtime-seeded marketplace order loop {run_id}', '{category}', 'FIXED',
    '{{"amount":8900,"currency":"RUB"}}'::jsonb, 'PUBLISHED', 'APPROVED', now(), now(), now()
);
INSERT INTO marketplace_offers (
    id, partner_id, subject_type, subject_id, title_override, description_override,
    status, currency, price_model, price_amount, terms, geo_scope, location_ids,
    entitlement_scope, allowed_subscription_codes, allowed_client_ids, created_at, updated_at
)
VALUES (
    '{offer_id}', '{partner_id}', 'SERVICE', '{product_id}', 'Smoke Marketplace Offer {run_id}',
    'Runtime-seeded offer for marketplace smoke', 'ACTIVE', 'RUB', 'FIXED', 8900,
    '{{"min_qty":1,"max_qty":1}}'::jsonb, 'ALL_PARTNER_LOCATIONS', '[]'::jsonb,
    'ALL_CLIENTS', '[]'::jsonb, '[]'::jsonb, now(), now()
);
"""
        psql(seed_sql)

        log("[5/11] Client browse and offers...")
        _, products = http_json("GET", f"{LEGACY_API_ROOT}/client/marketplace/products", token=client_token)
        items = products.get("items") or []
        target_product = next((item for item in items if str(item.get("id") or "") == product_id), None)
        require(bool(target_product and target_product.get("partner_name")), "marketplace products list did not expose the seeded product", products)

        _, product_detail = http_json("GET", f"{LEGACY_API_ROOT}/client/marketplace/products/{product_id}", token=client_token)
        require(
            str(product_detail.get("id") or "") == product_id
            and str((product_detail.get("partner") or {}).get("id") or "") == partner_id
            and str(product_detail.get("status") or "").upper() == "PUBLISHED",
            "marketplace product detail did not return the seeded partner/product truth",
            product_detail,
        )

        _, offers = http_json("GET", f"{LEGACY_API_ROOT}/client/marketplace/products/{product_id}/offers", token=client_token)
        offer_items = offers.get("items") or []
        require(
            offers.get("total") == 1 and len(offer_items) == 1 and str(offer_items[0].get("id") or "") == offer_id,
            "marketplace offers list did not expose the seeded offer",
            offers,
        )

        log("[6/11] Client create and pay order...")
        _, created = http_json(
            "POST",
            f"{LEGACY_API_ROOT}/marketplace/client/orders",
            token=client_token,
            body={"items": [{"offer_id": offer_id, "qty": 1}], "payment_method": "NEFT_INTERNAL"},
            expected=201,
        )
        order_id = str(created.get("id") or "")
        require(bool(order_id), "marketplace create response missing order id", created)
        require(
            str(created.get("status") or "").upper() == "PENDING_PAYMENT"
            and str(created.get("payment_status") or "").upper() == "UNPAID",
            "marketplace create response did not return PENDING_PAYMENT/UNPAID",
            created,
        )
        _, paid = http_json(
            "POST",
            f"{LEGACY_API_ROOT}/marketplace/client/orders/{order_id}:pay",
            token=client_token,
            body={"payment_method": "NEFT_INTERNAL"},
        )
        require(
            str(paid.get("status") or "").upper() == "PAID"
            and str(paid.get("payment_status") or "").upper() == "PAID",
            "marketplace pay response did not return PAID",
            paid,
        )

        log("[7/11] Partner confirm, proof, and complete...")
        _, partner_orders = http_json("GET", f"{LEGACY_API_ROOT}/v1/marketplace/partner/orders", token=partner_token)
        partner_order_ids = {str(item.get("id")) for item in (partner_orders.get("items") or [])}
        require(order_id in partner_order_ids, "partner orders list did not expose the paid order", partner_orders)

        _, confirmed = http_json(
            "POST",
            f"{LEGACY_API_ROOT}/v1/marketplace/partner/orders/{order_id}:confirm",
            token=partner_token,
        )
        require(str(confirmed.get("status") or "").upper() == "CONFIRMED_BY_PARTNER", "partner confirm did not return CONFIRMED_BY_PARTNER", confirmed)

        _, proof = http_json(
            "POST",
            f"{LEGACY_API_ROOT}/v1/marketplace/partner/orders/{order_id}/proofs",
            token=partner_token,
            body={"attachment_id": proof_attachment_id, "kind": "PHOTO", "note": "marketplace smoke proof"},
            expected=201,
        )
        require(
            bool(proof.get("id")) and str(proof.get("attachment_id") or "") == proof_attachment_id,
            "partner proof create did not persist the expected proof payload",
            proof,
        )

        _, completed = http_json(
            "POST",
            f"{LEGACY_API_ROOT}/v1/marketplace/partner/orders/{order_id}:complete",
            token=partner_token,
            body={"comment": "marketplace smoke complete"},
        )
        require(str(completed.get("status") or "").upper() == "COMPLETED", "partner complete did not return COMPLETED", completed)

        log("[8/11] Verify client incidents, consequence tail, and partner settlement readiness...")
        _, client_detail = http_json("GET", f"{LEGACY_API_ROOT}/marketplace/client/orders/{order_id}", token=client_token)
        require(
            str(client_detail.get("status") or "").upper() == "COMPLETED"
            and len(client_detail.get("proofs") or []) == 1
            and len(client_detail.get("lines") or []) == 1,
            "client order detail did not reflect COMPLETED state with proof",
            client_detail,
        )

        _, incidents = http_json("GET", f"{LEGACY_API_ROOT}/marketplace/client/orders/{order_id}/incidents", token=client_token)
        incident_items = incidents.get("items") or []
        require(
            int(incidents.get("total") or 0) >= 1
            and any(str(item.get("entity_id") or "") == order_id for item in incident_items),
            "order incidents did not expose the canonical order case",
            incidents,
        )

        _, client_consequences = http_json(
            "GET",
            f"{CORE_ROOT}/client/marketplace/orders/{order_id}/consequences",
            token=client_token,
        )
        require(isinstance(client_consequences.get("items"), list), "client consequences response must be mounted with items list", client_consequences)

        _, pending_settlement = http_json(
            "GET",
            f"{LEGACY_API_ROOT}/v1/marketplace/partner/orders/{order_id}/settlement",
            token=partner_token,
            expected=409,
        )
        require(
            first_error(pending_settlement) == "SETTLEMENT_NOT_FINALIZED",
            "partner settlement readiness tail did not return SETTLEMENT_NOT_FINALIZED",
            pending_settlement,
        )

        log("[9/11] Verify admin order detail, events, and hidden helper truth...")
        _, admin_detail = http_json("GET", f"{CORE_ROOT}/v1/admin/marketplace/orders/{order_id}", token=admin_token)
        require(
            str(admin_detail.get("status") or "").upper() == "COMPLETED"
            and len(admin_detail.get("proofs") or []) == 1,
            "admin order detail did not expose the completed order",
            admin_detail,
        )

        _, admin_events = http_json("GET", f"{CORE_ROOT}/v1/admin/marketplace/orders/{order_id}/events", token=admin_token)
        admin_event_types = [str(item.get("event_type") or "") for item in admin_events]
        require(
            admin_event_types == ["CREATED", "PAYMENT_PENDING", "PAYMENT_PAID", "CONFIRMED", "COMPLETED"],
            "admin order events did not expose the expected lifecycle",
            admin_events,
        )

        _, settlement_snapshot = http_json(
            "GET",
            f"{CORE_ROOT}/v1/admin/marketplace/orders/{order_id}/settlement-snapshot",
            token=admin_token,
        )
        require(
            str(settlement_snapshot.get("order_id") or "") == order_id
            and bool(settlement_snapshot.get("hash"))
            and not settlement_snapshot.get("finalized_at"),
            "admin settlement helper did not expose snapshot readiness truth",
            settlement_snapshot,
        )

        override_body = {
            "gross_amount": settlement_snapshot.get("gross_amount"),
            "platform_fee": settlement_snapshot.get("platform_fee"),
            "penalties": settlement_snapshot.get("penalties"),
            "partner_net": settlement_snapshot.get("partner_net"),
            "currency": settlement_snapshot.get("currency") or "RUB",
            "reason": "smoke_finalize_settlement_readiness",
        }
        _, finalized = http_json(
            "POST",
            f"{CORE_ROOT}/v1/admin/marketplace/orders/{order_id}/settlement-override",
            token=admin_token,
            body=override_body,
        )
        require(
            str(finalized.get("order_id") or "") == order_id
            and bool(finalized.get("finalized_at"))
            and bool(finalized.get("hash")),
            "admin settlement override did not finalize settlement snapshot",
            finalized,
        )

        _, ready_settlement = http_json(
            "GET",
            f"{LEGACY_API_ROOT}/v1/marketplace/partner/orders/{order_id}/settlement",
            token=partner_token,
        )
        ready_snapshot = ready_settlement.get("snapshot") or {}
        require(
            str(ready_settlement.get("order_id") or "") == order_id
            and bool(ready_snapshot.get("finalized_at"))
            and bool(ready_snapshot.get("hash"))
            and ready_settlement.get("partner_net") is not None,
            "partner settlement readiness did not return finalized 200 snapshot",
            ready_settlement,
        )

        _, admin_consequences = http_json(
            "GET",
            f"{CORE_ROOT}/v1/admin/marketplace/orders/{order_id}/consequences",
            token=admin_token,
        )
        require(isinstance(admin_consequences.get("items"), list), "admin consequences helper must be mounted with items list", admin_consequences)

        log("[10/11] Verify persisted order and canonical case rows...")
        verify_sql = f"""
SET search_path TO processing_core;
SELECT 'ORDER_STATUS=' || status::text FROM marketplace_orders WHERE id = '{order_id}';
SELECT 'ORDER_PAYMENT=' || payment_status::text FROM marketplace_orders WHERE id = '{order_id}';
SELECT 'ORDER_PROOFS=' || count(*)::text FROM marketplace_order_proofs WHERE order_id = '{order_id}';
SELECT 'ORDER_EVENTS=' || count(*)::text FROM marketplace_order_events WHERE order_id = '{order_id}';
SELECT 'CASE_KIND=' || kind::text FROM cases WHERE entity_id = '{order_id}' AND case_source_ref_type = 'MARKETPLACE_ORDER' ORDER BY created_at DESC LIMIT 1;
SELECT 'CASE_QUEUE=' || queue::text FROM cases WHERE entity_id = '{order_id}' AND case_source_ref_type = 'MARKETPLACE_ORDER' ORDER BY created_at DESC LIMIT 1;
SELECT 'CASE_EVENTS=' || count(*)::text FROM case_events WHERE case_id = (SELECT id FROM cases WHERE entity_id = '{order_id}' AND case_source_ref_type = 'MARKETPLACE_ORDER' ORDER BY created_at DESC LIMIT 1);
"""
        verify_output = psql(verify_sql)
        for needle in [
            "ORDER_STATUS=COMPLETED",
            "ORDER_PAYMENT=PAID",
            "ORDER_PROOFS=1",
            "ORDER_EVENTS=5",
            "CASE_KIND=order",
            "CASE_QUEUE=SUPPORT",
        ]:
            require(needle in verify_output, f"marketplace verification query missing {needle}", verify_output)
        case_events = [
            line.split("=", 1)[1]
            for line in verify_output.splitlines()
            if line.startswith("CASE_EVENTS=")
        ]
        require(bool(case_events and int(case_events[0]) > 0), "canonical marketplace case event timeline is empty", verify_output)

        evidence = evidence_doc(
            {
                "order_id": order_id,
                "client_id": client_id,
                "partner_id": partner_id,
                "product_id": product_id,
                "offer_id": offer_id,
                "client_consequences_items": len(client_consequences.get("items") or []),
                "admin_consequences_items": len(admin_consequences.get("items") or []),
                "partner_settlement_before_finalization": "409 SETTLEMENT_NOT_FINALIZED",
                "partner_settlement_after_finalization": {
                    "http_status": 200,
                    "hash": ready_snapshot.get("hash"),
                    "finalized_at": ready_snapshot.get("finalized_at"),
                    "partner_net": ready_settlement.get("partner_net"),
                },
                "admin_event_types": admin_event_types,
            }
        )

        log("[11/11] Marketplace order loop smoke completed.")
        log(f"[EVIDENCE] {EVIDENCE_PATH}")
        return 0
    except SmokeFailure as exc:
        failure_payload = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "surface": "marketplace_order_loop",
            "status": "FAILED",
            "error": str(exc),
        }
        EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE_PATH.write_text(json.dumps(failure_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[FAIL] {exc}", file=sys.stderr)
        print("[SMOKE] Failed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
