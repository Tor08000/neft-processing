import type { SupportTicketPriority, SupportTicketSlaStatus, SupportTicketStatus } from "../types/supportTickets";

export const supportTicketStatusLabel = (status: SupportTicketStatus): string => {
  switch (status) {
    case "OPEN":
      return "Открыто";
    case "IN_PROGRESS":
      return "В работе";
    case "CLOSED":
      return "Закрыто";
    default:
      return status;
  }
};

export const supportTicketStatusTone = (status: SupportTicketStatus): string => {
  switch (status) {
    case "OPEN":
      return "badge success";
    case "IN_PROGRESS":
      return "badge warning";
    case "CLOSED":
      return "badge muted";
    default:
      return "badge";
  }
};

export const supportTicketPriorityLabel = (priority: SupportTicketPriority): string => {
  switch (priority) {
    case "LOW":
      return "Низкий";
    case "NORMAL":
      return "Обычный";
    case "HIGH":
      return "Высокий";
    default:
      return priority;
  }
};

export const supportTicketSlaStatusLabel = (status: SupportTicketSlaStatus): string => {
  switch (status) {
    case "OK":
      return "🟢 OK";
    case "PENDING":
      return "🟡 Pending";
    case "BREACHED":
      return "🔴 Breached";
    default:
      return status;
  }
};

export const supportTicketSlaStatusTone = (status: SupportTicketSlaStatus): string => {
  switch (status) {
    case "OK":
      return "badge success";
    case "PENDING":
      return "badge warning";
    case "BREACHED":
      return "badge error";
    default:
      return "badge";
  }
};

export const supportTicketSlaRemainingLabel = (remainingMinutes: number | null, status: SupportTicketSlaStatus): string => {
  if (remainingMinutes === null || Number.isNaN(remainingMinutes)) {
    return "Данные SLA недоступны";
  }
  const absMinutes = Math.abs(remainingMinutes);
  if (status === "BREACHED" || remainingMinutes < 0) {
    return `Нарушено на ${absMinutes} мин`;
  }
  return `Осталось: ${absMinutes} мин`;
};
