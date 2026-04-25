from __future__ import annotations

from collections.abc import Iterable

ADMIN_CAPABILITY_KEYS = (
    "access",
    "ops",
    "runtime",
    "finance",
    "revenue",
    "cases",
    "commercial",
    "crm",
    "marketplace",
    "legal",
    "onboarding",
    "audit",
)

ADMIN_ACTION_KEYS = ("read", "operate", "approve", "override", "manage")

SUPERADMIN_ROLES = {"ADMIN", "NEFT_ADMIN", "NEFT_SUPERADMIN", "SUPERADMIN"}
PLATFORM_ADMIN_ROLES = {"PLATFORM_ADMIN"}
FINANCE_ADMIN_ROLES = {"NEFT_FINANCE", "FINANCE", "ADMIN_FINANCE"}
SUPPORT_ADMIN_ROLES = {"NEFT_SUPPORT", "SUPPORT"}
OPS_ADMIN_ROLES = {"NEFT_OPS", "OPS", "OPERATIONS"}
COMMERCIAL_ADMIN_ROLES = {"NEFT_SALES", "SALES", "CRM", "ADMIN_CRM"}
LEGAL_ADMIN_ROLES = {"NEFT_LEGAL", "LEGAL"}
OBSERVER_ADMIN_ROLES = {"AUDITOR", "ANALYST", "OBSERVER", "READ_ONLY_ANALYST", "NEFT_OBSERVER"}
PLATFORM_ADMIN_CAPABILITY_KEYS = tuple(
    capability for capability in ADMIN_CAPABILITY_KEYS if capability != "revenue"
)

ADMIN_ENVELOPE_ROLES = {
    *SUPERADMIN_ROLES,
    *PLATFORM_ADMIN_ROLES,
    *FINANCE_ADMIN_ROLES,
    *SUPPORT_ADMIN_ROLES,
    *OPS_ADMIN_ROLES,
    *COMMERCIAL_ADMIN_ROLES,
    *LEGAL_ADMIN_ROLES,
    *OBSERVER_ADMIN_ROLES,
}

ROLE_LEVEL_ORDER = (
    "superadmin",
    "platform_admin",
    "finance_admin",
    "support_admin",
    "operator",
    "commercial_admin",
    "legal_admin",
    "observer",
)


def normalize_admin_roles(raw_roles: Iterable[str]) -> set[str]:
    return {str(role).strip().upper() for role in raw_roles if str(role).strip()}


def _empty_permissions() -> dict[str, dict[str, bool]]:
    return {
        capability: {action: False for action in ADMIN_ACTION_KEYS}
        for capability in ADMIN_CAPABILITY_KEYS
    }


def _grant(
    permissions: dict[str, dict[str, bool]],
    capabilities: Iterable[str],
    *,
    read: bool = False,
    operate: bool = False,
    approve: bool = False,
    override: bool = False,
    manage: bool = False,
) -> None:
    for capability in capabilities:
        if capability not in permissions:
            continue
        state = permissions[capability]
        state["read"] = state["read"] or read
        state["operate"] = state["operate"] or operate
        state["approve"] = state["approve"] or approve
        state["override"] = state["override"] or override
        state["manage"] = state["manage"] or manage


def resolve_admin_levels(raw_roles: Iterable[str]) -> list[str]:
    roles = normalize_admin_roles(raw_roles)
    levels: list[str] = []

    if roles.intersection(SUPERADMIN_ROLES):
        levels.append("superadmin")
    if roles.intersection(PLATFORM_ADMIN_ROLES):
        levels.append("platform_admin")
    if roles.intersection(FINANCE_ADMIN_ROLES):
        levels.append("finance_admin")
    if roles.intersection(SUPPORT_ADMIN_ROLES):
        levels.append("support_admin")
    if roles.intersection(OPS_ADMIN_ROLES):
        levels.append("operator")
    if roles.intersection(COMMERCIAL_ADMIN_ROLES):
        levels.append("commercial_admin")
    if roles.intersection(LEGAL_ADMIN_ROLES):
        levels.append("legal_admin")
    if roles.intersection(OBSERVER_ADMIN_ROLES):
        levels.append("observer")

    ordered = [level for level in ROLE_LEVEL_ORDER if level in levels]
    return ordered or ["observer"]


def primary_admin_level(raw_roles: Iterable[str]) -> str:
    return resolve_admin_levels(raw_roles)[0]


def build_admin_permissions(raw_roles: Iterable[str]) -> dict[str, dict[str, bool]]:
    roles = normalize_admin_roles(raw_roles)
    permissions = _empty_permissions()

    if roles.intersection(SUPERADMIN_ROLES):
        _grant(
            permissions,
            ADMIN_CAPABILITY_KEYS,
            read=True,
            operate=True,
            approve=True,
            override=True,
            manage=True,
        )
    else:
        if roles.intersection(PLATFORM_ADMIN_ROLES):
            _grant(
                permissions,
                PLATFORM_ADMIN_CAPABILITY_KEYS,
                read=True,
                operate=True,
                approve=True,
                manage=True,
            )
            _grant(permissions, ("finance", "commercial", "legal"), override=True)

        if roles.intersection(FINANCE_ADMIN_ROLES):
            _grant(permissions, ("finance",), read=True, operate=True, approve=True, override=True)
            _grant(permissions, ("revenue",), read=True)
            _grant(permissions, ("runtime", "cases", "commercial", "audit"), read=True)

        if roles.intersection(SUPPORT_ADMIN_ROLES):
            _grant(permissions, ("cases",), read=True, operate=True, approve=True)
            _grant(permissions, ("onboarding",), read=True, operate=True, manage=True)
            _grant(permissions, ("marketplace", "finance", "commercial", "legal", "runtime", "audit"), read=True)

        if roles.intersection(OPS_ADMIN_ROLES):
            _grant(permissions, ("ops",), read=True, operate=True)
            _grant(permissions, ("runtime", "finance", "cases", "marketplace", "onboarding"), read=True)

        if roles.intersection(COMMERCIAL_ADMIN_ROLES):
            _grant(permissions, ("commercial",), read=True, operate=True, approve=True, override=True, manage=True)
            _grant(permissions, ("crm",), read=True, operate=True)
            _grant(permissions, ("onboarding",), read=True, operate=True)
            _grant(permissions, ("revenue",), read=True)
            _grant(permissions, ("cases", "marketplace"), read=True)

        if roles.intersection(LEGAL_ADMIN_ROLES):
            _grant(permissions, ("legal",), read=True, operate=True, approve=True)
            _grant(permissions, ("audit", "cases", "runtime"), read=True)

        if roles.intersection(OBSERVER_ADMIN_ROLES):
            _grant(
                permissions,
                ("runtime", "finance", "cases", "commercial", "crm", "marketplace", "legal", "audit"),
                read=True,
            )

    for capability in ADMIN_CAPABILITY_KEYS:
        state = permissions[capability]
        state["write"] = bool(
            state["operate"] or state["approve"] or state["override"] or state["manage"]
        )

    return permissions


def admin_capability_allows(raw_roles: Iterable[str], capability: str, action: str = "read") -> bool:
    permissions = build_admin_permissions(raw_roles)
    state = permissions.get(capability)
    if state is None:
        return False
    if action == "write":
        return bool(state.get("write"))
    if action not in ADMIN_ACTION_KEYS:
        return False
    return bool(state.get(action))


__all__ = [
    "ADMIN_ACTION_KEYS",
    "ADMIN_CAPABILITY_KEYS",
    "ADMIN_ENVELOPE_ROLES",
    "build_admin_permissions",
    "admin_capability_allows",
    "normalize_admin_roles",
    "primary_admin_level",
    "resolve_admin_levels",
]
