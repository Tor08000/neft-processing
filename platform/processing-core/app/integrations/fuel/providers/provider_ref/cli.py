from __future__ import annotations

import argparse
from datetime import datetime, timezone

from app.db import get_sessionmaker, init_db
from app.integrations.fuel.providers.adapter_registry import get_provider, load_default_providers
from app.integrations.fuel.providers.protocols import IngestBatchRequest
from app.services.fleet_offline_reconciliation import reconcile_offline_batches


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ProviderRef fuel tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest-batch")
    ingest.add_argument("--batch-key", required=True)
    ingest.add_argument("--csv", required=True)
    ingest.add_argument("--source", default="FILE_DROP")

    replay = subparsers.add_parser("replay-batch")
    replay.add_argument("--batch-key", required=True)
    replay.add_argument("--csv", required=True)
    replay.add_argument("--source", default="FILE_DROP")

    reconcile = subparsers.add_parser("offline-reconcile")
    reconcile.add_argument("--client-id", required=True)
    reconcile.add_argument("--period", required=True)

    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    init_db()
    session = get_sessionmaker()()
    try:
        load_default_providers()
        provider = get_provider("provider_ref")
        if args.command in {"ingest-batch", "replay-batch"}:
            with open(args.csv, "rb") as handle:
                payload = handle.read()
            result = provider.ingest_batch(
                session,
                IngestBatchRequest(
                    provider_code="provider_ref",
                    source=args.source,
                    batch_key=args.batch_key,
                    payload_ref=payload,
                    received_at=datetime.now(timezone.utc),
                ),
            )
            session.commit()
            print(
                f"batch={result.batch_id} status={result.status} total={result.records_total} "
                f"applied={result.records_applied} dup={result.records_duplicate} failed={result.records_failed}"
            )
            return
        if args.command == "offline-reconcile":
            run = reconcile_offline_batches(session, client_id=args.client_id, period_key=args.period)
            session.commit()
            print(f"run={run.id} status={run.status}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
