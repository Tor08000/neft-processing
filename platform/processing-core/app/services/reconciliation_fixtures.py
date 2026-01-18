from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import StringIO
from pathlib import Path
from typing import Iterable

from sqlalchemy import MetaData, Table, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.schema import DB_SCHEMA
from app.services.s3_storage import S3Storage


@dataclass(frozen=True)
class FixtureTransaction:
    posted_at: datetime
    amount: Decimal
    currency: str
    payer_inn: str | None
    payer_name: str | None
    reference: str | None
    purpose: str | None
    bank_tx_id: str


class FixtureStorage:
    def __init__(self) -> None:
        self.bucket = settings.NEFT_S3_BUCKET_SUPPORT_ATTACHMENTS
        self.storage = S3Storage(bucket=self.bucket)

    @staticmethod
    def normalize_filename(file_name: str) -> str:
        clean = Path(file_name).name.strip()
        return clean or "reconciliation-fixture"

    def build_object_key(self, *, bundle_id: str, file_name: str) -> str:
        safe_name = self.normalize_filename(file_name)
        return f"reconciliation-fixtures/{bundle_id}/{safe_name}"

    def put_bytes(self, *, object_key: str, payload: bytes, content_type: str) -> None:
        self.storage.put_bytes(object_key, payload, content_type=content_type)

    def presign_download(self, *, object_key: str, expires: int) -> str | None:
        return self.storage.presign(object_key, expires=expires)

    def exists(self, *, object_key: str) -> bool:
        return self.storage.exists(object_key)


def _table(db: Session, name: str) -> Table:
    return Table(name, MetaData(), autoload_with=db.get_bind(), schema=DB_SCHEMA)


def _resolve_invoice(db: Session, invoice_id: str) -> dict[str, object] | None:
    billing_invoices = _table(db, "billing_invoices")
    return (
        db.execute(select(billing_invoices).where(billing_invoices.c.id == invoice_id)).mappings().first()
    )


def _extract_amount(invoice: dict[str, object]) -> Decimal | None:
    for key in ("amount_total", "total_amount", "total_with_tax"):
        if key in invoice and invoice[key] is not None:
            return Decimal(str(invoice[key]))
    return None


def _extract_currency(invoice: dict[str, object]) -> str | None:
    currency = invoice.get("currency")
    if currency:
        return str(currency)
    return None


def _ensure_datetime(value: object | None) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return None


def _fixture_base_date(invoice: dict[str, object], seed: str | None) -> datetime:
    issued_at = _ensure_datetime(invoice.get("issued_at"))
    created_at = _ensure_datetime(invoice.get("created_at"))
    base = issued_at or created_at or datetime(2024, 1, 10, tzinfo=timezone.utc)
    seed_key = seed or str(invoice.get("id") or "")
    digest = hashlib.sha256(seed_key.encode("utf-8")).hexdigest()
    offset = int(digest[:4], 16) % 5
    return base + timedelta(days=offset)


def _seed_suffix(seed: str | None) -> str:
    if not seed:
        return "default"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]


def _format_amount(amount: Decimal) -> str:
    return f"{amount:.2f}"


def _build_bank_tx_id(
    *,
    scenario: str,
    invoice_id: str,
    tx_index: int,
    posted_at: datetime,
    amount: Decimal,
    seed: str | None,
) -> str:
    seed_part = _seed_suffix(seed)
    posted_date = posted_at.date().isoformat()
    return f"{scenario}-{invoice_id}-{tx_index}-{posted_date}-{_format_amount(amount)}-{seed_part}"


def build_fixture_transactions(
    *,
    scenario: str,
    invoice_id: str,
    base_amount: Decimal,
    currency: str,
    org_id: int,
    wrong_amount_mode: str | None,
    amount_delta: Decimal | None,
    payer_inn: str | None,
    payer_name: str | None,
    seed: str | None,
    invoice: dict[str, object],
) -> list[FixtureTransaction]:
    base_date = _fixture_base_date(invoice, seed)
    delta = amount_delta if amount_delta is not None else Decimal("1")
    if delta < 0:
        delta = abs(delta)

    def wrong_amount() -> Decimal:
        if wrong_amount_mode == "LESS":
            candidate = base_amount - delta
            return candidate if candidate > 0 else Decimal("0.01")
        return base_amount + delta

    transactions: list[FixtureTransaction] = []
    if scenario == "SCN3_DOUBLE_PAYMENT":
        for idx in range(2):
            posted_at = base_date + timedelta(minutes=idx)
            amount = base_amount
            bank_tx_id = _build_bank_tx_id(
                scenario=scenario,
                invoice_id=invoice_id,
                tx_index=idx + 1,
                posted_at=posted_at,
                amount=amount,
                seed=seed,
            )
            reference = f"INV-{invoice_id}-{idx + 1}"
            purpose = f"Invoice {invoice_id} payment"
            transactions.append(
                FixtureTransaction(
                    posted_at=posted_at,
                    amount=amount,
                    currency=currency,
                    payer_inn=payer_inn,
                    payer_name=payer_name,
                    reference=reference,
                    purpose=purpose,
                    bank_tx_id=bank_tx_id,
                )
            )
        return transactions

    if scenario == "SCN2_WRONG_AMOUNT":
        posted_at = base_date
        amount = wrong_amount()
        bank_tx_id = _build_bank_tx_id(
            scenario=scenario,
            invoice_id=invoice_id,
            tx_index=1,
            posted_at=posted_at,
            amount=amount,
            seed=seed,
        )
        reference = f"INV-{invoice_id}-WRONG"
        purpose = f"Invoice {invoice_id} payment"
        transactions.append(
            FixtureTransaction(
                posted_at=posted_at,
                amount=amount,
                currency=currency,
                payer_inn=payer_inn,
                payer_name=payer_name,
                reference=reference,
                purpose=purpose,
                bank_tx_id=bank_tx_id,
            )
        )
        return transactions

    if scenario == "SCN2_UNMATCHED":
        posted_at = base_date
        amount = base_amount + delta
        bank_tx_id = _build_bank_tx_id(
            scenario=scenario,
            invoice_id=invoice_id,
            tx_index=1,
            posted_at=posted_at,
            amount=amount,
            seed=seed,
        )
        reference = f"UNMATCHED-{org_id}"
        purpose = "Payment without invoice reference"
        transactions.append(
            FixtureTransaction(
                posted_at=posted_at,
                amount=amount,
                currency=currency,
                payer_inn=payer_inn,
                payer_name=payer_name,
                reference=reference,
                purpose=purpose,
                bank_tx_id=bank_tx_id,
            )
        )
        return transactions

    raise ValueError("unsupported_scenario")


def build_csv_fixture(transactions: Iterable[FixtureTransaction]) -> bytes:
    output = StringIO()
    fieldnames = [
        "date",
        "posted_at",
        "amount",
        "currency",
        "payer_inn",
        "payer_name",
        "reference",
        "purpose",
        "purpose_text",
        "bank_tx_id",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for tx in transactions:
        date_value = tx.posted_at.date().isoformat()
        writer.writerow(
            {
                "date": date_value,
                "posted_at": date_value,
                "amount": _format_amount(tx.amount),
                "currency": tx.currency,
                "payer_inn": tx.payer_inn or "",
                "payer_name": tx.payer_name or "",
                "reference": tx.reference or "",
                "purpose": tx.purpose or "",
                "purpose_text": tx.purpose or "",
                "bank_tx_id": tx.bank_tx_id,
            }
        )
    return output.getvalue().encode("utf-8")


def build_1c_fixture(transactions: Iterable[FixtureTransaction]) -> bytes:
    lines: list[str] = []
    for tx in transactions:
        lines.append("СекцияДокумент")
        lines.append(f"ДатаПоступило={tx.posted_at.date().isoformat()}")
        lines.append(f"Сумма={_format_amount(tx.amount)}")
        if tx.payer_name:
            lines.append(f"Плательщик={tx.payer_name}")
        if tx.payer_inn:
            lines.append(f"ПлательщикИНН={tx.payer_inn}")
        if tx.reference:
            lines.append(f"Номер={tx.reference}")
        if tx.purpose:
            lines.append(f"НазначениеПлатежа={tx.purpose}")
        lines.append(f"Валюта={tx.currency}")
        lines.append(f"Ид={tx.bank_tx_id}")
        lines.append("КонецДокумента")
        lines.append("")
    return "\n".join(lines).encode("utf-8")


def _mt940_date(dt: datetime) -> str:
    return dt.strftime("%y%m%d")


def build_mt940_fixture(transactions: Iterable[FixtureTransaction], *, currency: str) -> bytes:
    tx_list = list(transactions)
    base_date = tx_list[0].posted_at if tx_list else datetime(2024, 1, 10, tzinfo=timezone.utc)
    lines = [
        ":20:NEFTFIXTURE",
        ":25:NEFTBANK",
        ":28C:00001/001",
        f":60F:C{_mt940_date(base_date)}{currency}0,00",
    ]
    for tx in tx_list:
        amount = _format_amount(tx.amount).replace(".", ",")
        reference = tx.reference or tx.bank_tx_id
        lines.append(f":61:{_mt940_date(tx.posted_at)}C{amount}NTRF{reference}")
        if tx.purpose:
            lines.append(f":86:{tx.purpose}")
    lines.append(f":62F:C{_mt940_date(base_date)}{currency}0,00")
    return "\n".join(lines).encode("utf-8")


def generate_fixture_bundle(
    *,
    db: Session,
    scenario: str,
    invoice_id: str,
    org_id: int,
    currency: str,
    wrong_amount_mode: str | None,
    amount_delta: Decimal | None,
    payer_inn: str | None,
    payer_name: str | None,
    seed: str | None,
) -> tuple[dict[str, bytes], dict[str, object]]:
    invoice = _resolve_invoice(db, invoice_id)
    if invoice is None:
        raise ValueError("invoice_not_found")

    amount = _extract_amount(invoice)
    if amount is None:
        raise ValueError("invoice_amount_missing")

    resolved_currency = currency or _extract_currency(invoice) or "RUB"

    transactions = build_fixture_transactions(
        scenario=scenario,
        invoice_id=invoice_id,
        base_amount=amount,
        currency=resolved_currency,
        org_id=org_id,
        wrong_amount_mode=wrong_amount_mode,
        amount_delta=amount_delta,
        payer_inn=payer_inn,
        payer_name=payer_name,
        seed=seed,
        invoice=invoice,
    )

    files: dict[str, bytes] = {
        "CSV": build_csv_fixture(transactions),
        "CLIENT_BANK_1C": build_1c_fixture(transactions),
        "MT940": build_mt940_fixture(transactions, currency=resolved_currency),
    }

    return files, {"amount": amount, "currency": resolved_currency}
