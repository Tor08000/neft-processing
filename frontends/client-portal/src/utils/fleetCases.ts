import type { FleetCasePolicyAction, FleetCaseSeverity, FleetCaseSourceType, FleetCaseStatus } from "../types/fleetCases";

export const getFleetCaseStatusBadgeClass = (status?: FleetCaseStatus | null): string => {
  const normalized = status?.toString().toUpperCase();
  if (normalized === "OPEN") return "badge badge-warning";
  if (normalized === "IN_PROGRESS") return "badge badge-info";
  if (normalized === "CLOSED") return "badge badge-muted";
  return "badge badge-muted";
};

export const getFleetCaseSeverityBadgeClass = (severity?: FleetCaseSeverity | null): string => {
  const normalized = severity?.toString().toUpperCase();
  if (normalized === "LOW") return "badge badge-muted";
  if (normalized === "MEDIUM") return "badge badge-info";
  if (normalized === "HIGH") return "badge badge-warning";
  if (normalized === "CRITICAL") return "badge badge-error";
  return "badge badge-muted";
};

export const getFleetCasePolicyActionBadgeClass = (action?: FleetCasePolicyAction | null): string => {
  const normalized = action?.toString().toUpperCase();
  if (normalized?.includes("AUTO_BLOCK")) return "badge badge-warning";
  if (normalized?.includes("ESCALATE")) return "badge badge-info";
  return "badge badge-muted";
};

export const getFleetCaseTriggerBadgeClass = (trigger?: FleetCaseSourceType | null): string => {
  const normalized = trigger?.toString().toUpperCase();
  if (normalized === "LIMIT_BREACH") return "badge badge-warning";
  if (normalized === "ANOMALY") return "badge badge-info";
  return "badge badge-muted";
};
