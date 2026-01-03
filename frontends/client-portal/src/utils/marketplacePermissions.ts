import type { AuthSession } from "../api/types";
import { hasAnyRole } from "./roles";

export const canOrder = (user: AuthSession | null): boolean =>
  hasAnyRole(user, ["CLIENT_ADMIN", "CLIENT_FLEET_MANAGER", "CLIENT_OWNER"]);

export const canCancelMarketplaceOrder = (user: AuthSession | null): boolean =>
  hasAnyRole(user, ["CLIENT_ADMIN", "CLIENT_FLEET_MANAGER", "CLIENT_OWNER"]);
