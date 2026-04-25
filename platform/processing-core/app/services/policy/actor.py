from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal


@dataclass(frozen=True)
class ActorContext:
    actor_type: Literal["ADMIN", "CLIENT", "SYSTEM"]
    tenant_id: int
    client_id: str | None
    roles: set[str]
    user_id: str | None


def _coerce_actor_tenant_id(value: object) -> int:
    if value is None or isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return 0
    try:
        return int(text)
    except (TypeError, ValueError):
        return 0


def _normalize_roles(token: dict | None) -> set[str]:
    if not token:
        return set()
    roles: list[str] = []
    raw_roles = token.get("roles") or []
    if isinstance(raw_roles, str):
        raw_roles = [raw_roles]
    roles.extend([str(item) for item in raw_roles])
    role = token.get("role")
    if role:
        roles.append(str(role))
    return {item.strip().replace("-", "_").upper() for item in roles if str(item).strip()}


def _is_admin_role(roles: Iterable[str]) -> bool:
    return any(role == "SUPERADMIN" or role.startswith("ADMIN") for role in roles)


def _is_client_role(roles: Iterable[str]) -> bool:
    return any(role.startswith("CLIENT") for role in roles)


def actor_from_token(token: dict | None) -> ActorContext:
    roles = _normalize_roles(token)
    tenant_id = 0
    client_id = None
    user_id = None
    if token:
        tenant_id = _coerce_actor_tenant_id(token.get("tenant_id"))
        client_id = token.get("client_id")
        user_id = token.get("user_id") or token.get("sub")

    if _is_admin_role(roles):
        actor_type: Literal["ADMIN", "CLIENT", "SYSTEM"] = "ADMIN"
    elif _is_client_role(roles) or client_id:
        actor_type = "CLIENT"
    else:
        actor_type = "SYSTEM"

    return ActorContext(
        actor_type=actor_type,
        tenant_id=tenant_id,
        client_id=client_id,
        roles=roles,
        user_id=user_id,
    )


__all__ = ["ActorContext", "actor_from_token"]
