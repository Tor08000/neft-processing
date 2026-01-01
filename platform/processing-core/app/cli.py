from __future__ import annotations

import argparse
from datetime import datetime, timezone

from neft_shared.logging_setup import get_logger

from app.db import get_sessionmaker
from app.services.audit_purge_service import purge_ephemeral, purge_expired_attachments, purge_expired_exports

logger = get_logger(__name__)


def _format_result(result) -> str:
    sample = ", ".join(result.sample_ids)
    sample_msg = f" sample_ids=[{sample}]" if sample else ""
    return (
        f"{result.entity_type}: candidates={result.candidates} purged={result.purged} "
        f"skipped_hold={result.skipped_hold}{sample_msg}"
    )


def _run_audit_purge(args: argparse.Namespace) -> int:
    session = get_sessionmaker()()
    now = datetime.now(timezone.utc)
    try:
        exports_result = purge_expired_exports(
            session,
            now=now,
            dry_run=args.dry_run,
            purged_by=args.purged_by,
        )
        attachments_result = purge_expired_attachments(
            session,
            now=now,
            dry_run=args.dry_run,
            purged_by=args.purged_by,
        )
        ephemeral_result = purge_ephemeral(
            session,
            now=now,
            dry_run=args.dry_run,
            purged_by=args.purged_by,
        )
        if not args.dry_run:
            session.commit()
        logger.info("audit_purge_result", extra={"exports": exports_result, "attachments": attachments_result})
        print(_format_result(exports_result))
        print(_format_result(attachments_result))
        print(_format_result(ephemeral_result))
        return 0
    except Exception:
        session.rollback()
        logger.exception("audit_purge_failed")
        raise
    finally:
        session.close()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Core API management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    purge_parser = subparsers.add_parser("audit_purge", help="Purge expired audit artifacts")
    purge_parser.add_argument("--dry-run", action="store_true", help="Preview purge candidates")
    purge_parser.add_argument("--purged-by", default="audit_purge_cli", help="Actor name for purge log")
    purge_parser.set_defaults(handler=_run_audit_purge)

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    handler = args.handler
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
