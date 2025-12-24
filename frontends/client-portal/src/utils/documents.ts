const TYPE_LABELS: Record<string, string> = {
  INVOICE: "Счет",
  ACT: "Акт",
  RECONCILIATION_ACT: "Акт сверки",
  CLOSING_PACKAGE: "Пакет закрытия",
};

const STATUS_LABELS: Record<string, string> = {
  DRAFT: "Черновик",
  GENERATED: "Сформирован",
  SENT: "Отправлен",
  ACKNOWLEDGED: "Подтвержден",
  CANCELLED: "Отменен",
};

const STATUS_TONE: Record<string, "success" | "warning" | "danger" | "neutral"> = {
  DRAFT: "neutral",
  GENERATED: "warning",
  SENT: "neutral",
  ACKNOWLEDGED: "success",
  CANCELLED: "danger",
};

export const getDocumentTypeLabel = (value: string): string => TYPE_LABELS[value] ?? value;
export const getDocumentStatusLabel = (value: string): string => STATUS_LABELS[value] ?? value;
export const getDocumentStatusTone = (value: string): string => STATUS_TONE[value] ?? "neutral";
