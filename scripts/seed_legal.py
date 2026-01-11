#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCESSING_ROOT = ROOT / "platform" / "processing-core"
SHARED = ROOT / "shared" / "python"

for path in (PROCESSING_ROOT, SHARED):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.db import get_sessionmaker, init_db  # noqa: E402
from app.models.legal_document import LegalDocument, LegalDocumentContentType  # noqa: E402
from app.services.audit_service import RequestContext  # noqa: E402
from app.models.audit_log import ActorType  # noqa: E402
from app.services.legal import LegalService  # noqa: E402


SEED_DOCS = [
    {
        "code": "TERMS",
        "version": "1",
        "title": "Пользовательское соглашение",
        "locale": "ru",
    },
    {
        "code": "PRIVACY_POLICY",
        "version": "1",
        "title": "Политика конфиденциальности",
        "locale": "ru",
    },
    {
        "code": "CONSENT_PERSONAL_DATA",
        "version": "1",
        "title": "Согласие на обработку персональных данных",
        "locale": "ru",
    },
]


def main() -> None:
    init_db()
    SessionLocal = get_sessionmaker()
    now = datetime.now(timezone.utc)
    created = []
    ctx = RequestContext(actor_type=ActorType.SYSTEM, actor_id="seed_legal")
    with SessionLocal() as session:
        service = LegalService(session)
        for item in SEED_DOCS:
            exists = (
                session.query(LegalDocument)
                .filter(
                    LegalDocument.code == item["code"],
                    LegalDocument.version == item["version"],
                    LegalDocument.locale == item["locale"],
                )
                .first()
            )
            if exists:
                continue
            document = service.create_document(
                payload={
                    "code": item["code"],
                    "version": item["version"],
                    "title": item["title"],
                    "locale": item["locale"],
                    "effective_from": now,
                    "content_type": LegalDocumentContentType.MARKDOWN.value,
                    "content": "TBD",
                },
                actor_id="seed_legal",
                request_ctx=ctx,
            )
            document = service.publish_document(document=document, request_ctx=ctx)
            session.commit()
            created.append(item["code"])

    print(json.dumps({"created": created}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
