export const INVOICE_STATUS_LABELS: Record<string, string> = {
  DRAFT: "Черновик",
  ISSUED: "Выставлен",
  SENT: "Выставлен",
  PARTIALLY_PAID: "Частично оплачен",
  PAID: "Оплачен",
  OVERDUE: "Просрочен",
  VOID: "Аннулирован",
};

const STATUS_TONES: Record<string, string> = {
  DRAFT: "muted",
  ISSUED: "warn",
  SENT: "warn",
  PARTIALLY_PAID: "warn",
  PAID: "ok",
  OVERDUE: "error",
  VOID: "muted",
};

export const getInvoiceStatusLabel = (status: string): string => INVOICE_STATUS_LABELS[status] ?? status;

export const getInvoiceStatusTone = (status: string): string => STATUS_TONES[status] ?? "muted";
