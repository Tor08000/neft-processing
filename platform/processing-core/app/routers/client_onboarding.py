from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.db.schema import DB_SCHEMA
from app.models.client import Client
from app.models.client_onboarding import ClientOnboarding, ClientOnboardingContract
from app.schemas.client_onboarding import (
    OnboardingContractGenerateResponse,
    OnboardingContractResponse,
    OnboardingContractSignResponse,
    OnboardingProfileRequest,
    OnboardingProfileResponse,
    OnboardingStatusResponse,
)
from app.services import client_auth
from app.services.feature_flags import is_enabled
from app.services.s3_storage import S3Storage


router = APIRouter(prefix="/client/onboarding", tags=["client-onboarding"])

SELF_SIGNUP_FLAG = "self_signup_enabled"
AUTO_ACTIVATE_FLAG = "auto_activate_after_sign"
CONTRACT_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[1] / "assets" / "client_onboarding_contract_v1.pdf"
)


def _require_self_signup_enabled(db: Session) -> None:
    if not is_enabled(db, SELF_SIGNUP_FLAG, default=False):
        raise HTTPException(status_code=403, detail="self_signup_disabled")


def _table_exists(db: Session, name: str) -> bool:
    try:
        inspector = inspect(db.get_bind())
        return inspector.has_table(name, schema=DB_SCHEMA)
    except Exception:
        return False


def _table_columns(db: Session, name: str) -> set[str]:
    try:
        inspector = inspect(db.get_bind())
        return {column["name"] for column in inspector.get_columns(name, schema=DB_SCHEMA)}
    except Exception:
        return set()


def _require_onboarding_tables(db: Session, tables: list[str]) -> None:
    missing = [table for table in tables if not _table_exists(db, table)]
    if missing:
        raise HTTPException(
            status_code=409,
            detail={
                "error": {
                    "type": "onboarding_context_missing",
                    "reason_code": "ONBOARDING_CONTEXT_MISSING",
                    "message": f"Missing onboarding tables: {', '.join(missing)}",
                }
            },
        )


def _get_owner_id(token: dict) -> str:
    owner_id = token.get("user_id") or token.get("sub")
    if not owner_id:
        raise HTTPException(status_code=403, detail="Missing user context")
    return str(owner_id)


def _get_onboarding(db: Session, *, token: dict, owner_id: str) -> ClientOnboarding | None:
    client_id = token.get("client_id")
    if client_id:
        return db.query(ClientOnboarding).filter(ClientOnboarding.client_id == str(client_id)).one_or_none()
    return (
        db.query(ClientOnboarding)
        .filter(ClientOnboarding.owner_user_id == owner_id)
        .one_or_none()
    )


def _load_contract_template() -> bytes:
    if not CONTRACT_TEMPLATE_PATH.exists():
        raise HTTPException(status_code=500, detail="contract_template_missing")
    return CONTRACT_TEMPLATE_PATH.read_bytes()


def _store_contract_pdf(client_id: str, contract_id: str, payload: bytes) -> str:
    key = f"client-onboarding/{client_id}/{contract_id}/contract_v1.pdf"
    try:
        storage = S3Storage()
        storage.ensure_bucket()
        return storage.put_bytes(key, payload)
    except Exception:
        return f"stub://{key}"


@router.get("/status", response_model=OnboardingStatusResponse)
def onboarding_status(
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
):
    _require_self_signup_enabled(db)
    _require_onboarding_tables(db, ["client_onboarding"])
    owner_id = _get_owner_id(token)
    onboarding = _get_onboarding(db, token=token, owner_id=owner_id)
    if not onboarding:
        return OnboardingStatusResponse(step="PROFILE", status="DRAFT")
    client_type = onboarding.client_type or None
    if onboarding.profile_json and not client_type:
        client_type = onboarding.profile_json.get("client_type")
    return OnboardingStatusResponse(step=onboarding.step, status=onboarding.status, client_type=client_type)


@router.post("/profile-legacy", response_model=OnboardingProfileResponse)
def onboarding_profile(
    payload: OnboardingProfileRequest,
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
):
    _require_self_signup_enabled(db)
    _require_onboarding_tables(db, ["clients", "client_onboarding"])
    owner_id = _get_owner_id(token)
    onboarding = _get_onboarding(db, token=token, owner_id=owner_id)
    token_client_id = str(token.get("client_id") or "").strip() or None
    token_client_uuid = None
    if token_client_id:
        try:
            token_client_uuid = UUID(token_client_id)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="invalid_client_id")

    org_type = payload.client_type or payload.org_type
    client = None
    if token_client_uuid is not None:
        client = db.query(Client).filter(Client.id == token_client_uuid).one_or_none()
    elif onboarding:
        try:
            onboarding_client_uuid = UUID(str(onboarding.client_id))
        except (TypeError, ValueError):
            onboarding_client_uuid = None
        if onboarding_client_uuid is not None:
            client = db.query(Client).filter(Client.id == onboarding_client_uuid).one_or_none()

    client_columns = _table_columns(db, "clients")
    if client is None:
        client_payload = {
            "id": uuid4(),
            "name": payload.name,
            "legal_name": None if str(org_type).upper() == "INDIVIDUAL" else payload.name,
            "full_name": payload.name if str(org_type).upper() == "INDIVIDUAL" else None,
            "status": "ONBOARDING",
        }
        if token_client_uuid is not None:
            client_payload["id"] = token_client_uuid
        if "inn" in client_columns:
            client_payload["inn"] = payload.inn
        if "ogrn" in client_columns:
            client_payload["ogrn"] = payload.ogrn
        if "org_type" in client_columns:
            client_payload["org_type"] = org_type
        client = Client(**client_payload)
        db.add(client)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="onboarding_profile_conflict") from exc

    if payload.name:
        client.name = payload.name
        client.legal_name = None if str(org_type).upper() == "INDIVIDUAL" else payload.name
        client.full_name = payload.name if str(org_type).upper() == "INDIVIDUAL" else None
    if "inn" in client_columns:
        client.inn = payload.inn
    if "ogrn" in client_columns:
        client.ogrn = payload.ogrn
    if "org_type" in client_columns:
        client.org_type = org_type
    if "status" in client_columns and client.status != "ONBOARDING":
        client.status = "ONBOARDING"

    profile_data = payload.model_dump()
    if payload.model_extra:
        profile_data.update(payload.model_extra)
    org_type = org_type or profile_data.get("org_type") or profile_data.get("client_type")
    if org_type and "org_type" not in profile_data:
        profile_data["org_type"] = org_type

    if onboarding is None:
        onboarding = ClientOnboarding(
            client_id=str(client.id),
            owner_user_id=owner_id,
            step="CONTRACT",
            status="DRAFT",
            client_type=org_type,
            profile_json=profile_data,
        )
        db.add(onboarding)
    else:
        onboarding.step = "CONTRACT"
        onboarding.status = "DRAFT"
        onboarding.profile_json = profile_data
        onboarding.client_type = org_type or onboarding.client_type

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="onboarding_profile_conflict") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="onboarding_profile_unavailable") from exc
    return OnboardingProfileResponse(step="CONTRACT", status="DRAFT")


@router.post("/contract/generate", response_model=OnboardingContractGenerateResponse)
def onboarding_contract_generate(
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
):
    _require_self_signup_enabled(db)
    _require_onboarding_tables(db, ["client_onboarding", "client_onboarding_contracts"])
    owner_id = _get_owner_id(token)
    onboarding = _get_onboarding(db, token=token, owner_id=owner_id)
    if not onboarding:
        raise HTTPException(status_code=400, detail="onboarding_profile_required")

    if onboarding.contract_id:
        existing = (
            db.query(ClientOnboardingContract)
            .filter(ClientOnboardingContract.id == onboarding.contract_id)
            .one_or_none()
        )
        if existing:
            return OnboardingContractGenerateResponse(
                contract_id=str(existing.id),
                pdf_url=existing.pdf_url,
                version=int(existing.version or 1),
            )

    payload = _load_contract_template()
    contract = ClientOnboardingContract(
        client_id=str(onboarding.client_id),
        status="DRAFT",
        pdf_url="",
        version=1,
    )
    db.add(contract)
    db.flush()

    pdf_url = _store_contract_pdf(str(onboarding.client_id), str(contract.id), payload)
    contract.pdf_url = pdf_url
    onboarding.contract_id = str(contract.id)
    onboarding.step = "CONTRACT"
    onboarding.status = "DRAFT"
    db.commit()

    return OnboardingContractGenerateResponse(
        contract_id=str(contract.id),
        pdf_url=pdf_url,
        version=int(contract.version or 1),
    )


@router.get("/contract", response_model=OnboardingContractResponse)
def onboarding_contract(
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
):
    _require_self_signup_enabled(db)
    _require_onboarding_tables(db, ["client_onboarding", "client_onboarding_contracts"])
    owner_id = _get_owner_id(token)
    onboarding = _get_onboarding(db, token=token, owner_id=owner_id)
    if not onboarding or not onboarding.contract_id:
        raise HTTPException(status_code=404, detail="contract_not_found")

    contract = (
        db.query(ClientOnboardingContract)
        .filter(ClientOnboardingContract.id == onboarding.contract_id)
        .one_or_none()
    )
    if not contract:
        raise HTTPException(status_code=404, detail="contract_not_found")

    return OnboardingContractResponse(
        contract_id=str(contract.id),
        status=contract.status,
        pdf_url=contract.pdf_url,
        version=int(contract.version or 1),
    )


@router.post("/contract/sign", response_model=OnboardingContractSignResponse)
def onboarding_contract_sign(
    request: Request,
    token: dict = Depends(client_auth.require_onboarding_user),
    db: Session = Depends(get_db),
):
    _require_self_signup_enabled(db)
    _require_onboarding_tables(db, ["clients", "client_onboarding", "client_onboarding_contracts"])
    owner_id = _get_owner_id(token)
    onboarding = _get_onboarding(db, token=token, owner_id=owner_id)
    if not onboarding or not onboarding.contract_id:
        raise HTTPException(status_code=404, detail="contract_not_found")

    contract = (
        db.query(ClientOnboardingContract)
        .filter(ClientOnboardingContract.id == onboarding.contract_id)
        .one_or_none()
    )
    if not contract:
        raise HTTPException(status_code=404, detail="contract_not_found")

    payload = _load_contract_template()
    now = datetime.now(timezone.utc)
    signature_meta = {
        "ip": getattr(request.client, "host", None),
        "user_agent": request.headers.get("user-agent"),
        "timestamp": now.isoformat(),
        "doc_hash": sha256(payload).hexdigest(),
    }
    contract.status = "SIGNED_SIMPLE"
    contract.signed_at = now
    contract.signature_meta = signature_meta

    try:
        onboarding_client_uuid = UUID(str(onboarding.client_id))
    except (TypeError, ValueError):
        onboarding_client_uuid = None
    client = (
        db.query(Client).filter(Client.id == onboarding_client_uuid).one_or_none()
        if onboarding_client_uuid is not None
        else None
    )
    if not client:
        raise HTTPException(status_code=404, detail="client_not_found")

    auto_activate = is_enabled(db, AUTO_ACTIVATE_FLAG, default=False)
    client.status = "ACTIVE" if auto_activate else "PENDING_ACTIVATION"
    onboarding.step = "ACTIVATION"
    onboarding.status = client.status
    db.commit()

    return OnboardingContractSignResponse(status=client.status)
