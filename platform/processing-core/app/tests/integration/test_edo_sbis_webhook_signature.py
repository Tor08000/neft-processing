from __future__ import annotations

import hmac
import json
import os
from datetime import datetime, timezone
from hashlib import sha256

from fastapi.testclient import TestClient

from app.db import get_sessionmaker
from app.db.types import new_uuid_str
from app.main import app
from app.models.edo import (
    EdoAccount,
    EdoDocument,
    EdoDocumentKind,
    EdoDocumentStatus,
    EdoProvider,
    EdoSubjectType,
)


def test_sbis_webhook_signature_updates_document() -> None:
    session = get_sessionmaker()()
    account_id = new_uuid_str()
    secret = "test-secret"
    os.environ["SBIS_TEST_WEBHOOK_SECRET"] = secret
    os.environ["SBIS_TEST_CREDENTIALS"] = json.dumps({"base_url": "http://sbis.test"})
    try:
        account = EdoAccount(
            id=account_id,
            provider=EdoProvider.SBIS,
            name="Test SBIS",
            box_id="box-1",
            credentials_ref="env:SBIS_TEST_CREDENTIALS",
            webhook_secret_ref="env:SBIS_TEST_WEBHOOK_SECRET",
            is_active=True,
        )
        session.add(account)
        doc = EdoDocument(
            id=new_uuid_str(),
            provider=EdoProvider.SBIS,
            account_id=account_id,
            subject_type=EdoSubjectType.CLIENT,
            subject_id="client-1",
            document_registry_id=new_uuid_str(),
            document_kind=EdoDocumentKind.INVOICE,
            provider_doc_id="doc-123",
            status=EdoDocumentStatus.SENT,
            counterparty_id=new_uuid_str(),
            send_dedupe_key="dedupe-1",
        )
        session.add(doc)
        session.commit()

        payload = {
            "event_id": "evt-1",
            "provider_doc_id": "doc-123",
            "status": "SIGNED",
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
        payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), payload_bytes, sha256).hexdigest()
        with TestClient(app) as client:
            response = client.post(
                "/integrations/edo/sbis/webhook",
                headers={
                    "x-sbis-signature": signature,
                    "x-edo-account-id": account_id,
                },
                json=payload,
            )
        assert response.status_code == 200
    finally:
        session.close()
