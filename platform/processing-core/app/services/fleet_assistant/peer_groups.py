from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PeerGroup:
    scope: str
    tenant_id: int | None
    client_id: str | None
    network_id: str | None
    window_days: int
    as_of: datetime | None


def resolve_peer_group(
    *,
    entity_type: str,
    tenant_id: int | None,
    client_id: str | None,
    network_id: str | None,
    window_days: int,
    as_of: datetime | None,
    use_tenant_scope: bool,
) -> PeerGroup:
    if entity_type == "STATION":
        scope = "TENANT"
    elif use_tenant_scope and tenant_id is not None:
        scope = "TENANT"
    else:
        scope = "CLIENT"
    return PeerGroup(
        scope=scope,
        tenant_id=tenant_id,
        client_id=client_id,
        network_id=network_id,
        window_days=window_days,
        as_of=as_of,
    )


__all__ = ["PeerGroup", "resolve_peer_group"]
