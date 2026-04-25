from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

from fastapi import HTTPException, Request
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies.admin import require_admin_user
from app.api.dependencies.support import support_user_dep
from app.db import Base, get_db
from app.deps.db import get_db as get_deps_db
from app.models.audit_log import AuditLog
from app.models.cases import Case, CaseComment, CaseEvent, CaseSnapshot
from app.models.client import Client
from app.models.client_invitations import ClientInvitation
from app.models.decision_memory import DecisionMemoryRecord
from app.models.support_request import SupportRequest
from app.models.support_ticket import SupportTicket, SupportTicketAttachment, SupportTicketComment

CASES_TEST_TABLES = (
    Case.__table__,
    CaseSnapshot.__table__,
    CaseComment.__table__,
    CaseEvent.__table__,
    DecisionMemoryRecord.__table__,
)

SUPPORT_REQUEST_TEST_TABLES = (
    AuditLog.__table__,
    SupportRequest.__table__,
    Case.__table__,
    CaseSnapshot.__table__,
    CaseComment.__table__,
    CaseEvent.__table__,
    DecisionMemoryRecord.__table__,
)

SUPPORT_TICKET_TEST_TABLES = (
    AuditLog.__table__,
    SupportTicket.__table__,
    SupportTicketComment.__table__,
    SupportTicketAttachment.__table__,
    Case.__table__,
    CaseSnapshot.__table__,
    CaseComment.__table__,
    CaseEvent.__table__,
    DecisionMemoryRecord.__table__,
)

ADMIN_CLIENT_INVITATION_TEST_TABLES = (
    Client.__table__,
    ClientInvitation.__table__,
)


def _decode_support_claims(request: Request) -> dict[str, Any]:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing_bearer_token")

    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="missing_bearer_token")

    claims = dict(jwt.get_unverified_claims(token))
    roles = {str(role).upper() for role in claims.get("roles") or []}
    role = claims.get("role")
    if role:
        roles.add(str(role).upper())

    if claims.get("client_id"):
        claims["is_client"] = True
    if claims.get("partner_id"):
        claims["is_partner"] = True
    if any("ADMIN" in role_name for role_name in roles):
        claims["is_admin"] = True
    return claims


def support_user_override(request: Request) -> dict[str, Any]:
    return _decode_support_claims(request)


def require_admin_user_override(request: Request) -> dict[str, Any]:
    claims = _decode_support_claims(request)
    if not claims.get("is_admin"):
        raise HTTPException(status_code=403, detail="forbidden")
    return claims


def cases_dependency_overrides() -> dict[Callable[..., Any], Callable[..., Any]]:
    return {support_user_dep: support_user_override}


def support_requests_dependency_overrides() -> dict[Callable[..., Any], Callable[..., Any]]:
    return {
        support_user_dep: support_user_override,
        require_admin_user: require_admin_user_override,
    }


@contextmanager
def scoped_session_context(*, tables: Sequence[Any]) -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        bind=engine,
    )

    if tables:
        Base.metadata.create_all(bind=engine, tables=list(tables))

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        if tables:
            Base.metadata.drop_all(bind=engine, tables=list(tables))
        engine.dispose()


@contextmanager
def router_client_context(
    *,
    router: APIRouter,
    prefix: str = "",
    db_session: Session | None = None,
    dependency_overrides: Mapping[Callable[..., Any], Callable[..., Any]] | None = None,
) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(router, prefix=prefix)

    if db_session is not None:
        def override_get_db():
            try:
                yield db_session
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_deps_db] = override_get_db

    if dependency_overrides:
        for dependency, override in dependency_overrides.items():
            app.dependency_overrides[dependency] = override

    with TestClient(app) as client:
        yield client
