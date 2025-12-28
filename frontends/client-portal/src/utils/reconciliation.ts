export const RECONCILIATION_STATUS_LABELS: Record<string, string> = {
  REQUESTED: "Запрошен",
  IN_PROGRESS: "В работе",
  GENERATED: "Сформирован",
  SENT: "Отправлен",
  ACKNOWLEDGED: "Подтвержден",
  REJECTED: "Отклонен",
  CANCELLED: "Отменен",
};

const STATUS_TONES: Record<string, string> = {
  REQUESTED: "pill--warning",
  IN_PROGRESS: "pill--warning",
  GENERATED: "pill--success",
  SENT: "pill--success",
  ACKNOWLEDGED: "pill--success",
  REJECTED: "pill--danger",
  CANCELLED: "pill--neutral",
};

export const getReconciliationStatusLabel = (status: string): string =>
  RECONCILIATION_STATUS_LABELS[status] ?? status;

export const getReconciliationStatusTone = (status: string): string =>
  STATUS_TONES[status] ?? "pill--neutral";
