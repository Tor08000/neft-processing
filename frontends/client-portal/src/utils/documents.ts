const TYPE_LABELS: Record<string, string> = {
  INVOICE: "Счет",
  ACT: "Акт",
  RECONCILIATION_ACT: "Акт сверки",
  CLOSING_PACKAGE: "Закрывающий пакет (closing_package)",
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

export const getDocumentTypeLabel = (value: string): string => TYPE_LABELS[value] ?? value;
export const getDocumentStatusLabel = (value: string): string => STATUS_LABELS[value] ?? value;
export const getDocumentStatusTone = (value: string): string => STATUS_TONE[value] ?? "neutral";
