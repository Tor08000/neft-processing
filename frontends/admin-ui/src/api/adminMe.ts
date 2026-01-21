import { CORE_API_BASE } from "./base";
import type { AdminErrorPayload, AdminMeResponse } from "../types/admin";

type PortalMeResponse = {
  actor_type: string;
  user: {
    id: string;
    email?: string | null;
  };
  user_roles?: string[];
  org_roles?: string[];
};

export class AdminMeError extends Error {
  status: number;
  payload?: AdminErrorPayload;

  constructor(status: number, message: string, payload?: AdminErrorPayload) {
    super(message);
    this.name = "AdminMeError";
    this.status = status;
    this.payload = payload;
  }
}

const buildUrl = (path: string) => `${CORE_API_BASE}${path}`;

const buildPermissions = (roles: string[]) => {
  const roleSet = new Set(roles.map((role) => role.toUpperCase()));
  const superadminEnabled =
    roleSet.has("NEFT_SUPERADMIN") || roleSet.has("NEFT_ADMIN") || roleSet.has("ADMIN") || roleSet.has("SUPERADMIN");
  const ops = { read: roleSet.has("NEFT_OPS"), write: false };
  const finance = { read: roleSet.has("NEFT_FINANCE"), write: roleSet.has("NEFT_FINANCE") };
  const sales = { read: roleSet.has("NEFT_SALES"), write: false };
  const legal = { read: roleSet.has("NEFT_LEGAL"), write: false };
  if (superadminEnabled) {
    return {
      ops: { read: true, write: true },
      finance: { read: true, write: true },
      sales: { read: true, write: true },
      legal: { read: true, write: true },
      superadmin: { read: true, write: true },
    };
  }
  return {
    ops,
    finance,
    sales,
    legal,
    superadmin: { read: superadminEnabled, write: superadminEnabled },
  };
};

export async function fetchAdminMe(token: string): Promise<AdminMeResponse> {
  const response = await fetch(buildUrl("/portal/me"), {
    method: "GET",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
  });

  const isJson = response.headers.get("content-type")?.includes("application/json");
  if (response.ok) {
    const portal = (await response.json()) as PortalMeResponse;
    const roles = portal.user_roles?.length ? portal.user_roles : portal.org_roles ?? [];
    return {
      admin_user: {
        id: portal.user?.id ?? "unknown",
        email: portal.user?.email ?? null,
        roles,
        issuer: null,
      },
      permissions: buildPermissions(roles),
      env: {
        name: (import.meta.env.MODE ?? "dev") as AdminMeResponse["env"]["name"],
        build: import.meta.env.VITE_BUILD_SHA ?? "unknown",
        region: import.meta.env.VITE_REGION ?? "local",
      },
    };
  }

  const payload = isJson ? ((await response.json()) as AdminErrorPayload) : undefined;
  const message = payload?.message ?? `Admin me failed with status ${response.status}`;
  throw new AdminMeError(response.status, message, payload);
}
