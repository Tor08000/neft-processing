export const AUDIT_EVENT_LABELS: Record<string, string> = {
  INVOICE_CREATED: "Счет создан",
  INVOICE_STATUS_CHANGED: "Статус счёта изменён",
  PAYMENT_POSTED: "Платёж принят",
  PAYMENT_FAILED: "Платёж отклонён",
  REFUND_POSTED: "Возврат выполнен",
  INVOICE_PDF_DOWNLOADED: "PDF скачан",
  INVOICE_DOWNLOADED: "PDF скачан",
  DOCUMENT_ACKNOWLEDGED: "Документ подтвержден",
  INVOICE_MESSAGE_CREATED: "Сообщение по счету",
  RECONCILIATION_REQUEST_CREATED: "Акт сверки запрошен",
  RECONCILIATION_GENERATED: "Акт сверки сформирован",
  RECONCILIATION_SENT: "Акт сверки отправлен",
  RECONCILIATION_ACKNOWLEDGED: "Акт сверки подтвержден",
};

export const getAuditEventLabel = (eventType: string): string => AUDIT_EVENT_LABELS[eventType] ?? eventType;

export const getActorLabel = (actorType?: string | null): string => {
  if (!actorType) return "Система";
  if (actorType === "USER") return "Вы";
  if (actorType === "SERVICE") return "Сервис";
  return "Система";
};
