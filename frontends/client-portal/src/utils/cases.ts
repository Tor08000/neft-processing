import type { CasePriority, CaseStatus } from "../types/cases";

export const caseStatusLabel = (status: CaseStatus): string => {
  const map: Record<CaseStatus, string> = {
    TRIAGE: "Триаж",
    IN_PROGRESS: "В работе",
    RESOLVED: "Решён",
    CLOSED: "Закрыт",
  };
  return map[status] ?? status;
};

export const casePriorityLabel = (priority: CasePriority): string => {
  const map: Record<CasePriority, string> = {
    LOW: "Низкий",
    MEDIUM: "Средний",
    HIGH: "Высокий",
    CRITICAL: "Критический",
  };
  return map[priority] ?? priority;
};

export const caseStatusTone = (status: CaseStatus): string => {
  if (status === "RESOLVED") return "badge success";
  if (status === "CLOSED") return "badge neutral";
  return "badge";
};
