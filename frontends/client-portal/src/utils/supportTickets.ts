import type { SupportTicketPriority, SupportTicketStatus } from "../types/supportTickets";

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
