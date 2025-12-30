const TYPE_LABELS: Record<string, string> = {
  INVOICE: "Счет",
  ACT: "Акт",
  RECONCILIATION_ACT: "Акт сверки",
  CLOSING_PACKAGE: "Закрывающий пакет (closing_package)",
  OFFER: "Оферта",
};

const STATUS_LABELS: Record<string, string> = {
  DRAFT: "DRAFT",
  ISSUED: "ISSUED",
  ACKNOWLEDGED: "ACKNOWLEDGED",
  FINALIZED: "FINALIZED",
  VOID: "VOID",
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

export const getDocumentTypeLabel = (value: string): string => TYPE_LABELS[value] ?? value;
export const getDocumentStatusLabel = (value: string): string => STATUS_LABELS[value] ?? value;
export const getDocumentStatusTone = (value: string): string => STATUS_TONE[value] ?? "neutral";
export const getSignatureTone = (value?: string | null): "success" | "warning" | "danger" | "neutral" => {
  if (!value) return "neutral";
  return SIGNATURE_TONE[value] ?? "neutral";
};
export const getEdoTone = (value?: string | null): "success" | "warning" | "danger" | "neutral" => {
  if (!value) return "neutral";
  return EDO_TONE[value] ?? "neutral";
};
