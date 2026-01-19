from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from app.config import settings
from app.models.partner_core import PartnerProfile
from app.models.partner_legal import PartnerLegalDetails, PartnerLegalPack, PartnerLegalProfile
from app.services.partner_legal_service import PartnerLegalService
from app.services.s3_storage import S3Storage


@dataclass(frozen=True)
class PartnerLegalPackResult:
    pack_id: str
    partner_id: str
    format: str
    object_key: str
    pack_hash: str
    metadata: dict[str, Any]
    download_url: str | None


class PartnerLegalPackService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def generate_pack(self, *, partner_id: str, format: str) -> PartnerLegalPackResult:
        legal_service = PartnerLegalService(self.db)
        profile = legal_service.get_profile(partner_id=partner_id)
        details = legal_service.get_details(partner_id=partner_id)
        tax_context = legal_service.build_tax_context(profile=profile)
        profile_payload = self._profile_payload(profile)
        details_payload = self._details_payload(details)
        payload = {
            "partner_id": partner_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "legal_profile": profile_payload,
            "legal_details": details_payload,
            "tax_context": tax_context.to_dict() if tax_context else None,
            "pricing_model": self._resolve_pricing_model(partner_id),
            "sla": self._resolve_sla(partner_id),
        }
        pdf_bytes = self._render_pdf(payload)
        pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
        pack_format = format.upper()
        if pack_format == "ZIP":
            pack_bytes = self._build_zip(pdf_bytes=pdf_bytes, payload=payload)
            pack_hash = hashlib.sha256(pack_bytes).hexdigest()
            extension = "zip"
        else:
            pack_bytes = pdf_bytes
            pack_hash = pdf_hash
            extension = "pdf"
        object_key = f"partner-legal-packs/{partner_id}/{pack_hash}.{extension}"
        bucket = settings.NEFT_S3_BUCKET_DOCUMENTS or settings.NEFT_S3_BUCKET
        storage = S3Storage(bucket=bucket)
        content_type = "application/zip" if extension == "zip" else "application/pdf"
        storage.put_bytes(object_key, pack_bytes, content_type=content_type)
        download_url = storage.presign(object_key) or storage.public_url(object_key)
        pack = PartnerLegalPack(
            partner_id=partner_id,
            format=pack_format,
            object_key=object_key,
            pack_hash=pack_hash,
            metadata_json=payload,
        )
        self.db.add(pack)
        self.db.flush()
        return PartnerLegalPackResult(
            pack_id=str(pack.id),
            partner_id=partner_id,
            format=pack_format,
            object_key=object_key,
            pack_hash=pack_hash,
            metadata=payload,
            download_url=download_url,
        )

    def list_history(self, *, partner_id: str) -> list[PartnerLegalPack]:
        return (
            self.db.query(PartnerLegalPack)
            .filter(PartnerLegalPack.partner_id == partner_id)
            .order_by(PartnerLegalPack.created_at.desc())
            .all()
        )

    def _profile_payload(self, profile: PartnerLegalProfile | None) -> dict[str, Any] | None:
        if profile is None:
            return None
        return {
            "legal_type": profile.legal_type.value if hasattr(profile.legal_type, "value") else str(profile.legal_type),
            "country": profile.country,
            "tax_residency": profile.tax_residency,
            "tax_regime": profile.tax_regime.value if profile.tax_regime else None,
            "vat_applicable": bool(profile.vat_applicable),
            "vat_rate": float(profile.vat_rate) if profile.vat_rate is not None else None,
            "legal_status": profile.legal_status.value if hasattr(profile.legal_status, "value") else str(profile.legal_status),
        }

    def _details_payload(self, details: PartnerLegalDetails | None) -> dict[str, Any] | None:
        if details is None:
            return None
        return {
            "legal_name": details.legal_name,
            "inn": details.inn,
            "kpp": details.kpp,
            "ogrn": details.ogrn,
            "passport": details.passport,
            "bank_account": details.bank_account,
            "bank_bic": details.bank_bic,
            "bank_name": details.bank_name,
        }

    def _resolve_pricing_model(self, partner_id: str) -> dict[str, Any]:
        try:
            org_id = int(partner_id)
        except (TypeError, ValueError):
            org_id = None
        profile = self.db.query(PartnerProfile).filter(PartnerProfile.org_id == org_id).one_or_none() if org_id else None
        return {
            "model": "marketplace",
            "partner_profile_id": str(profile.id) if profile else None,
        }

    def _resolve_sla(self, partner_id: str) -> dict[str, Any]:
        return {"model": "standard", "notes": "SLA определяется действующими соглашениями"}

    def _build_zip(self, *, pdf_bytes: bytes, payload: dict[str, Any]) -> bytes:
        buffer = io.BytesIO()
        meta = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        timestamp = datetime.now(timezone.utc)
        zip_timestamp = (timestamp.year, timestamp.month, timestamp.day, timestamp.hour, timestamp.minute, timestamp.second)
        with ZipFile(buffer, mode="w") as archive:
            for name, data, content_type in [
                ("partner_legal_pack.pdf", pdf_bytes, "application/pdf"),
                ("metadata.json", meta, "application/json"),
            ]:
                info = ZipInfo(filename=name, date_time=zip_timestamp)
                info.compress_type = ZIP_DEFLATED
                info.extra = b""
                info.comment = b""
                archive.writestr(info, data)
        return buffer.getvalue()

    def _render_pdf(self, payload: dict[str, Any]) -> bytes:
        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4, invariant=1)
        height = A4[1]
        x = 20 * mm
        y = height - 20 * mm
        pdf.setFont("Helvetica-Bold", 14)
        y = self._line(pdf, "Partner Legal Pack", x=x, y=y)
        pdf.setFont("Helvetica", 10)
        y = self._line(pdf, f"Partner ID: {payload.get('partner_id')}", x=x, y=y)
        y = self._line(pdf, f"Generated at: {payload.get('generated_at')}", x=x, y=y)
        y -= 6 * mm
        y = self._section(pdf, "Legal Profile", payload.get("legal_profile"), x=x, y=y)
        y = self._section(pdf, "Legal Details", payload.get("legal_details"), x=x, y=y)
        y = self._section(pdf, "Tax Context", payload.get("tax_context"), x=x, y=y)
        y = self._section(pdf, "Pricing Model", payload.get("pricing_model"), x=x, y=y)
        self._section(pdf, "SLA", payload.get("sla"), x=x, y=y)
        pdf.showPage()
        pdf.save()
        return buffer.getvalue()

    def _section(self, pdf: canvas.Canvas, title: str, data: dict[str, Any] | None, *, x: float, y: float) -> float:
        pdf.setFont("Helvetica-Bold", 12)
        y = self._line(pdf, title, x=x, y=y)
        pdf.setFont("Helvetica", 10)
        if not data:
            y = self._line(pdf, "—", x=x, y=y)
            y -= 4 * mm
            return y
        for key, value in data.items():
            y = self._line(pdf, f"{key}: {value}", x=x, y=y)
            if y < 20 * mm:
                pdf.showPage()
                y = A4[1] - 20 * mm
                pdf.setFont("Helvetica", 10)
        y -= 4 * mm
        return y

    @staticmethod
    def _line(pdf: canvas.Canvas, text: str, *, x: float, y: float) -> float:
        pdf.drawString(x, y, text)
        return y - 6 * mm


__all__ = ["PartnerLegalPackResult", "PartnerLegalPackService"]
