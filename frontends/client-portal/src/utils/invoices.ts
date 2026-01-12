export const INVOICE_STATUS_LABELS: Record<string, string> = {
  SENT: "Выставлен",
  PARTIALLY_PAID: "Частично оплачен",
  PAID: "Оплачен",
};

const STATUS_TONES: Record<string, string> = {
  SENT: "warn",
  PARTIALLY_PAID: "warn",
  PAID: "ok",
};

export const getInvoiceStatusLabel = (status: string): string => INVOICE_STATUS_LABELS[status] ?? status;

export const getInvoiceStatusTone = (status: string): string => STATUS_TONES[status] ?? "muted";
