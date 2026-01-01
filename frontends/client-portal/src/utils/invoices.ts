export const INVOICE_STATUS_LABELS: Record<string, string> = {
  SENT: "Выставлен",
  PARTIALLY_PAID: "Частично оплачен",
  PAID: "Оплачен",
};

const STATUS_TONES: Record<string, string> = {
  SENT: "warning",
  PARTIALLY_PAID: "warning",
  PAID: "success",
};

export const getInvoiceStatusLabel = (status: string): string => INVOICE_STATUS_LABELS[status] ?? status;

export const getInvoiceStatusTone = (status: string): string => STATUS_TONES[status] ?? "neutral";
