from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models.internal_ledger import InternalLedgerEntry, InternalLedgerTransaction, InternalLedgerTransactionType
from app.services.internal_ledger import InternalLedgerLine, InternalLedgerService
from app.models.internal_ledger import InternalLedgerAccountType, InternalLedgerEntryDirection

engine = create_engine("sqlite:///./test_idempotency.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


def setup_module(module):
    tables = [
        Base.metadata.tables["internal_ledger_accounts"],
        Base.metadata.tables["internal_ledger_transactions"],
        Base.metadata.tables["internal_ledger_entries"],
        Base.metadata.tables["audit_log"],
    ]
    for table in reversed(tables):
        table.drop(bind=engine, checkfirst=True)
    for table in tables:
        table.create(bind=engine, checkfirst=True)


def teardown_module(module):
    tables = [
        Base.metadata.tables["internal_ledger_entries"],
        Base.metadata.tables["internal_ledger_transactions"],
        Base.metadata.tables["internal_ledger_accounts"],
        Base.metadata.tables["audit_log"],
    ]
    for table in tables:
        table.drop(bind=engine, checkfirst=True)


def _post_once(key: str) -> tuple[str, bool]:
    db = SessionLocal()
    try:
        result = InternalLedgerService(db).post_transaction(
            tenant_id=77,
            transaction_type=InternalLedgerTransactionType.ADJUSTMENT,
            external_ref_type="audit",
            external_ref_id="idem-1",
            idempotency_key=key,
            posted_at=datetime.now(timezone.utc),
            meta={"source": "test"},
            entries=[
                InternalLedgerLine(
                    account_type=InternalLedgerAccountType.CLIENT_AR,
                    client_id="client-1",
                    direction=InternalLedgerEntryDirection.DEBIT,
                    amount=100,
                    currency="RUB",
                ),
                InternalLedgerLine(
                    account_type=InternalLedgerAccountType.CLIENT_CASH,
                    client_id="client-1",
                    direction=InternalLedgerEntryDirection.CREDIT,
                    amount=100,
                    currency="RUB",
                ),
            ],
        )
        db.commit()
        return str(result.transaction.id), result.is_replay
    finally:
        db.close()


def test_same_idempotency_key_same_result_and_no_duplicate_entries():
    tx1, replay1 = _post_once("idem-same-key")
    tx2, replay2 = _post_once("idem-same-key")

    assert tx1 == tx2
    assert replay1 is False
    assert replay2 is True

    db = SessionLocal()
    try:
        tx_count = db.query(InternalLedgerTransaction).filter(InternalLedgerTransaction.idempotency_key == "idem-same-key").count()
        entries_count = db.query(InternalLedgerEntry).join(
            InternalLedgerTransaction,
            InternalLedgerEntry.ledger_transaction_id == InternalLedgerTransaction.id,
        ).filter(InternalLedgerTransaction.idempotency_key == "idem-same-key").count()
    finally:
        db.close()

    assert tx_count == 1
    assert entries_count == 2


def test_concurrent_retries_create_exactly_one_transaction():
    key = "idem-concurrent-1"
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(_post_once, [key] * 10))

    transaction_ids = {tx_id for tx_id, _ in results}
    assert len(transaction_ids) == 1
    assert sum(1 for _, replay in results if replay is False) == 1
    assert sum(1 for _, replay in results if replay is True) == 9

    db = SessionLocal()
    try:
        tx_count = db.query(InternalLedgerTransaction).filter(InternalLedgerTransaction.idempotency_key == "idem-concurrent-1").count()
        entries_count = db.query(InternalLedgerEntry).join(
            InternalLedgerTransaction,
            InternalLedgerEntry.ledger_transaction_id == InternalLedgerTransaction.id,
        ).filter(InternalLedgerTransaction.idempotency_key == "idem-concurrent-1").count()
    finally:
        db.close()

    assert tx_count == 1
    assert entries_count == 2
