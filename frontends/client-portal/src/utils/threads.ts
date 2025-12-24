export const THREAD_STATUS_LABELS: Record<string, string> = {
  OPEN: "Открыт",
  WAITING_SUPPORT: "Ожидает поддержку",
  WAITING_CLIENT: "Ожидает клиента",
  RESOLVED: "Решен",
  CLOSED: "Закрыт",
};

const STATUS_TONES: Record<string, string> = {
  OPEN: "pill--warning",
  WAITING_SUPPORT: "pill--warning",
  WAITING_CLIENT: "pill--warning",
  RESOLVED: "pill--success",
  CLOSED: "pill--neutral",
};

export const getThreadStatusLabel = (status: string): string => THREAD_STATUS_LABELS[status] ?? status;

export const getThreadStatusTone = (status: string): string => STATUS_TONES[status] ?? "pill--neutral";
