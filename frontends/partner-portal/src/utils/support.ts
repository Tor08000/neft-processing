import type { SupportRequestStatus, SupportRequestSubjectType } from "../types/support";

export const supportStatusLabel = (status: SupportRequestStatus): string => {
  switch (status) {
    case "OPEN":
      return "Открыто";
    case "IN_PROGRESS":
      return "В работе";
    case "WAITING":
      return "Ожидает данных";
    case "RESOLVED":
      return "Решено";
    case "CLOSED":
      return "Закрыто";
    default:
      return status;
  }
};

export const supportStatusTone = (status: SupportRequestStatus): string => {
  switch (status) {
    case "OPEN":
    case "IN_PROGRESS":
    case "WAITING":
      return "pending";
    case "RESOLVED":
      return "success";
    case "CLOSED":
      return "error";
    default:
      return "pending";
  }
};

export const supportSubjectLabel = (subjectType: SupportRequestSubjectType, subjectId?: string | null): string => {
  const suffix = subjectId ? ` #${subjectId.slice(0, 8)}` : "";
  switch (subjectType) {
    case "ORDER":
      return `ORDER${suffix}`;
    case "DOCUMENT":
      return `DOCUMENT${suffix}`;
    case "PAYOUT":
      return `PAYOUT${suffix}`;
    case "SETTLEMENT":
      return `SETTLEMENT${suffix}`;
    case "INTEGRATION":
      return `INTEGRATION${suffix}`;
    case "OTHER":
      return "Прочее";
    default:
      return subjectType;
  }
};
