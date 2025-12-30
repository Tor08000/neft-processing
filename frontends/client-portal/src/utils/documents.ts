import { translate } from "../i18n";

const TYPE_LABELS: Record<string, string> = {
  INVOICE: "documentsPage.types.INVOICE",
  ACT: "documentsPage.types.ACT",
  RECONCILIATION_ACT: "documentsPage.types.RECONCILIATION_ACT",
  CLOSING_PACKAGE: "documentsPage.types.CLOSING_PACKAGE",
  OFFER: "documentsPage.types.OFFER",
};

const STATUS_LABELS: Record<string, string> = {
  DRAFT: "statuses.documents.DRAFT",
  ISSUED: "statuses.documents.ISSUED",
  ACKNOWLEDGED: "statuses.documents.ACKNOWLEDGED",
  FINALIZED: "statuses.documents.FINALIZED",
  VOID: "statuses.documents.VOID",
};

const STATUS_TONE: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  DRAFT: "neutral",
  ISSUED: "warning",
  ACKNOWLEDGED: "success",
  FINALIZED: "success",
  VOID: "danger",
};

const SIGNATURE_TONE: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  SIGNED: "success",
  VERIFIED: "success",
  REQUESTED: "warning",
  SIGNING: "warning",
  FAILED: "danger",
  REJECTED: "danger",
};

const EDO_TONE: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  SENT: "warning",
  DELIVERED: "warning",
  SIGNED: "success",
  SIGNED_BY_COUNTERPARTY: "success",
  REJECTED: "danger",
  FAILED: "danger",
};

const SIGNATURE_LABELS: Record<string, string> = {
  SIGNED: "statuses.signature.SIGNED",
  VERIFIED: "statuses.signature.VERIFIED",
  REQUESTED: "statuses.signature.REQUESTED",
  SIGNING: "statuses.signature.SIGNING",
  FAILED: "statuses.signature.FAILED",
  REJECTED: "statuses.signature.REJECTED",
};

const EDO_LABELS: Record<string, string> = {
  SENT: "statuses.edo.SENT",
  DELIVERED: "statuses.edo.DELIVERED",
  SIGNED: "statuses.edo.SIGNED",
  SIGNED_BY_COUNTERPARTY: "statuses.edo.SIGNED_BY_COUNTERPARTY",
  REJECTED: "statuses.edo.REJECTED",
  FAILED: "statuses.edo.FAILED",
};

export const getDocumentTypeLabel = (value: string): string => translate(TYPE_LABELS[value] ?? value);
export const getDocumentStatusLabel = (value: string): string => translate(STATUS_LABELS[value] ?? value);
export const getDocumentStatusTone = (value: string): string => STATUS_TONE[value] ?? "neutral";
export const getSignatureStatusLabel = (value?: string | null): string => {
  if (!value) return translate("common.notAvailable");
  return translate(SIGNATURE_LABELS[value] ?? value);
};
export const getEdoStatusLabel = (value?: string | null): string => {
  if (!value) return translate("common.notAvailable");
  return translate(EDO_LABELS[value] ?? value);
};
export const getSignatureTone = (value?: string | null): "success" | "warning" | "danger" | "neutral" => {
  if (!value) return "neutral";
  return SIGNATURE_TONE[value] ?? "neutral";
};
export const getEdoTone = (value?: string | null): "success" | "warning" | "danger" | "neutral" => {
  if (!value) return "neutral";
  return EDO_TONE[value] ?? "neutral";
};
