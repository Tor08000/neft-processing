import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "platform" / "processing-core"))

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("NEFT_AUTO_CREATE_SCHEMA", "true")

from app.db import get_sessionmaker, init_db, reset_engine  # noqa: E402
from app.integrations.fuel.providers.adapter_registry import load_default_providers, get_provider  # noqa: E402
from app.integrations.fuel.providers.protocols import IngestBatchRequest  # noqa: E402
from app.integrations.fuel.models import FuelProviderBatch  # noqa: E402
from app.models.fuel import FuelCard, FuelCardStatus, FuelTransaction  # noqa: E402


def _load_fixture() -> bytes:
    return Path("tests_host/fixtures/fuel/provider_ref_transactions.csv").read_bytes()


def test_fuel_provider_replay_batch():
    reset_engine()
    init_db()
    session = get_sessionmaker()()
    try:
        card = FuelCard(
            tenant_id=1,
            client_id="client-1",
            card_token="CARD-1001",
            card_alias="CARD-1001",
            masked_pan="****1111",
            status=FuelCardStatus.ACTIVE,
        )
        session.add(card)
        session.commit()

        load_default_providers()
        provider = get_provider("provider_ref")

        payload = _load_fixture()
        result = provider.ingest_batch(
            session,
            IngestBatchRequest(
                provider_code="provider_ref",
                source="FILE_DROP",
                batch_key="B1",
                payload_ref=payload,
                received_at=card.created_at,
            ),
        )
        session.commit()
        assert result.records_applied == 2

        replay_result = provider.ingest_batch(
            session,
            IngestBatchRequest(
                provider_code="provider_ref",
                source="FILE_DROP",
                batch_key="B1",
                payload_ref=payload,
                received_at=card.created_at,
            ),
        )
        session.commit()
        assert replay_result.records_applied == 0
        assert replay_result.records_duplicate == 2

        txs = session.query(FuelTransaction).filter(FuelTransaction.provider_code == "provider_ref").all()
        assert len(txs) == 2
        hashes = {tx.provider_tx_id: tx.content_hash for tx in txs}
        assert all(hashes.values())

        mutated_payload = _load_fixture().decode("utf-8").replace("500.00", "700.00")
        mutation_result = provider.ingest_batch(
            session,
            IngestBatchRequest(
                provider_code="provider_ref",
                source="FILE_DROP",
                batch_key="B2",
                payload_ref=mutated_payload.encode("utf-8"),
                received_at=card.created_at,
            ),
        )
        session.commit()
        assert mutation_result.records_failed == 1
        batch = (
            session.query(FuelProviderBatch)
            .filter(FuelProviderBatch.provider_code == "provider_ref")
            .filter(FuelProviderBatch.batch_key == "B2")
            .one()
        )
        assert batch.status.value == "FAILED"
        assert batch.error == "provider_mutation_detected"
    finally:
        session.close()
