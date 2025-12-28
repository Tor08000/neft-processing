from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.money_flow_v3 import MoneyFlowLink, MoneyFlowLinkNodeType, MoneyFlowLinkType


@dataclass(frozen=True)
class MoneyFlowLinkSpec:
    src_type: MoneyFlowLinkNodeType
    src_id: str
    link_type: MoneyFlowLinkType
    dst_type: MoneyFlowLinkNodeType
    dst_id: str
    meta: Mapping[str, object] | None = None

    def key(self) -> tuple[str, str, str, str, str]:
        return (
            self.src_type.value,
            self.src_id,
            self.link_type.value,
            self.dst_type.value,
            self.dst_id,
        )


@dataclass
class MoneyFlowGraphBuilder:
    tenant_id: int
    client_id: str
    _links: dict[tuple[str, str, str, str, str], MoneyFlowLinkSpec] = field(default_factory=dict)

    def add_link(
        self,
        *,
        src_type: MoneyFlowLinkNodeType,
        src_id: str,
        link_type: MoneyFlowLinkType,
        dst_type: MoneyFlowLinkNodeType,
        dst_id: str,
        meta: Mapping[str, object] | None = None,
    ) -> None:
        spec = MoneyFlowLinkSpec(
            src_type=src_type,
            src_id=src_id,
            link_type=link_type,
            dst_type=dst_type,
            dst_id=dst_id,
            meta=meta,
        )
        self._links.setdefault(spec.key(), spec)

    def build(self) -> list[MoneyFlowLinkSpec]:
        return list(self._links.values())


def ensure_money_flow_links(
    db: Session,
    *,
    tenant_id: int,
    client_id: str,
    links: Iterable[MoneyFlowLinkSpec],
) -> list[MoneyFlowLink]:
    created: list[MoneyFlowLink] = []
    for link in links:
        existing = (
            db.execute(
                select(MoneyFlowLink)
                .where(MoneyFlowLink.tenant_id == tenant_id)
                .where(MoneyFlowLink.src_type == link.src_type)
                .where(MoneyFlowLink.src_id == link.src_id)
                .where(MoneyFlowLink.link_type == link.link_type)
                .where(MoneyFlowLink.dst_type == link.dst_type)
                .where(MoneyFlowLink.dst_id == link.dst_id)
            )
            .scalars()
            .first()
        )
        if existing:
            created.append(existing)
            continue
        record = MoneyFlowLink(
            tenant_id=tenant_id,
            client_id=client_id,
            src_type=link.src_type,
            src_id=link.src_id,
            link_type=link.link_type,
            dst_type=link.dst_type,
            dst_id=link.dst_id,
            meta=dict(link.meta) if link.meta else None,
        )
        db.add(record)
        created.append(record)
    return created


__all__ = ["MoneyFlowGraphBuilder", "MoneyFlowLinkSpec", "ensure_money_flow_links"]
