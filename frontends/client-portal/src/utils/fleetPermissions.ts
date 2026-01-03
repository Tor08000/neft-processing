import type { AuthSession } from "../api/types";
import { hasAnyRole } from "./roles";
import type { FleetGroupRole } from "../types/fleet";

const manageRoles = ["CLIENT_OWNER", "CLIENT_FLEET_MANAGER"] as const;
const viewRoles = ["CLIENT_OWNER", "CLIENT_FLEET_MANAGER", "CLIENT_USER", "CLIENT_ACCOUNTANT"] as const;

export const canManageFleetCards = (user: AuthSession | null): boolean => hasAnyRole(user, [...manageRoles]);
export const canManageFleetGroups = (user: AuthSession | null): boolean => hasAnyRole(user, [...manageRoles]);
export const canManageFleetEmployees = (user: AuthSession | null): boolean => hasAnyRole(user, [...manageRoles]);
export const canManageFleetLimits = (user: AuthSession | null): boolean => hasAnyRole(user, [...manageRoles]);
export const canViewFleetSpend = (user: AuthSession | null): boolean => hasAnyRole(user, [...manageRoles]);
export const canViewFleetNotifications = (user: AuthSession | null): boolean => hasAnyRole(user, [...viewRoles]);
export const canAckFleetNotifications = (user: AuthSession | null): boolean => hasAnyRole(user, [...manageRoles]);
export const canAdminFleetNotifications = (user: AuthSession | null): boolean => hasAnyRole(user, ["CLIENT_OWNER"]);
export const canViewFleetIncidents = (user: AuthSession | null): boolean =>
  hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_FLEET_MANAGER", "CLIENT_USER", "CLIENT_ACCOUNTANT", "CLIENT_ADMIN"]);
export const canStartFleetIncidents = (user: AuthSession | null): boolean =>
  hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_FLEET_MANAGER", "CLIENT_ADMIN"]);
export const canCloseFleetIncidents = (user: AuthSession | null): boolean =>
  hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ADMIN"]);

const roleOrder: FleetGroupRole[] = ["viewer", "manager", "admin"];

export const normalizeGroupRole = (role?: FleetGroupRole | null, fallback: FleetGroupRole = "viewer"): FleetGroupRole =>
  role ?? fallback;

export const isGroupRoleAtLeast = (role: FleetGroupRole, required: FleetGroupRole): boolean => {
  const roleIndex = roleOrder.indexOf(role);
  const requiredIndex = roleOrder.indexOf(required);
  if (roleIndex === -1 || requiredIndex === -1) {
    return false;
  }
  return roleIndex >= requiredIndex;
};

export const deriveGroupRole = (user: AuthSession | null, apiRole?: FleetGroupRole | null): FleetGroupRole => {
  if (apiRole) return apiRole;
  if (hasAnyRole(user, [...manageRoles])) return "admin";
  return "viewer";
};
