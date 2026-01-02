export type FleetPolicyRole = "viewer" | "manager" | "admin";
export type FleetPolicyScope = "CLIENT" | "GROUP" | "CARD" | string;

export const canManagePolicies = (userRole: FleetPolicyRole, scopeType: FleetPolicyScope): boolean => {
  if (userRole === "admin") return true;
  if (userRole === "manager") return scopeType === "GROUP";
  return false;
};

export const canViewExecutions = (userRole: FleetPolicyRole): boolean => userRole === "admin";
