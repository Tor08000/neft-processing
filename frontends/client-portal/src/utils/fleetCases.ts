import type { FleetCasePolicyAction, FleetCaseSeverity, FleetCaseSourceType, FleetCaseStatus } from "../types/fleetCases";

export const getFleetCaseStatusBadgeClass = (status?: FleetCaseStatus | null): string => {
  const normalized = status?.toString().toUpperCase();
  if (normalized === "OPEN") return "neft-chip neft-chip-warn";
  if (normalized === "IN_PROGRESS") return "neft-chip neft-chip-info";
  if (normalized === "CLOSED") return "neft-chip neft-chip-muted";
  return "neft-chip neft-chip-muted";
};

export const getFleetCaseSeverityBadgeClass = (severity?: FleetCaseSeverity | null): string => {
  const normalized = severity?.toString().toUpperCase();
  if (normalized === "LOW") return "neft-chip neft-chip-muted";
  if (normalized === "MEDIUM") return "neft-chip neft-chip-info";
  if (normalized === "HIGH") return "neft-chip neft-chip-warn";
  if (normalized === "CRITICAL") return "neft-chip neft-chip-err";
  return "neft-chip neft-chip-muted";
};

export const getFleetCasePolicyActionBadgeClass = (action?: FleetCasePolicyAction | null): string => {
  const normalized = action?.toString().toUpperCase();
  if (normalized?.includes("AUTO_BLOCK")) return "neft-chip neft-chip-warn";
  if (normalized?.includes("ESCALATE")) return "neft-chip neft-chip-info";
  return "neft-chip neft-chip-muted";
};

export const getFleetCaseTriggerBadgeClass = (trigger?: FleetCaseSourceType | null): string => {
  const normalized = trigger?.toString().toUpperCase();
  if (normalized === "LIMIT_BREACH") return "neft-chip neft-chip-warn";
  if (normalized === "ANOMALY") return "neft-chip neft-chip-info";
  return "neft-chip neft-chip-muted";
};
