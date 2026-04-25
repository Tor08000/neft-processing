import { ADMIN_API_BASE, normalizeAdminPath } from "./base";
import type { AdminErrorPayload, AdminMeResponse } from "../types/admin";
import { buildAdminPermissions, primaryAdminRoleLevel, resolveAdminRoleLevels } from "../admin/access";

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

const buildUrl = (path: string) => `${ADMIN_API_BASE}${normalizeAdminPath(path)}`;

const parseJsonSafely = async <T>(response: Response): Promise<T | null> => {
  try {
    return (await response.json()) as T;
  } catch (err) {
    return null;
  }
};

export async function fetchAdminMe(token: string): Promise<AdminMeResponse> {
  const response = await fetch(buildUrl("/me"), {
    method: "GET",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
  });

  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const requestId = response.headers.get("x-request-id") ?? response.headers.get("x-correlation-id");

  if (response.ok) {
    const payload = isJson ? await parseJsonSafely<AdminMeResponse | PortalMeResponse>(response) : null;
    if (!payload) {
      throw new AdminMeError(502, "Invalid JSON response from admin me", {
        error: "admin_error",
        message: "Invalid JSON response from admin me",
        status: 502,
        request_id: requestId,
      });
    }
    if ("admin_user" in payload) {
      const env = payload.environment ?? payload.env;
      const roles = payload.roles ?? payload.admin_user.roles ?? [];
      const permissions = payload.permissions ?? buildAdminPermissions(roles);
      return {
        ...payload,
        roles,
        primary_role_level: payload.primary_role_level ?? primaryAdminRoleLevel(roles),
        role_levels: payload.role_levels ?? resolveAdminRoleLevels(roles),
        permissions,
        env,
        environment: env,
        read_only: payload.read_only ?? false,
        audit_context: payload.audit_context,
      };
    }
    const roles = payload.user_roles?.length ? payload.user_roles : payload.org_roles ?? [];
    return {
      admin_user: {
        id: payload.user?.id ?? "unknown",
        email: payload.user?.email ?? null,
        roles,
        issuer: null,
      },
      roles,
      primary_role_level: primaryAdminRoleLevel(roles),
      role_levels: resolveAdminRoleLevels(roles),
      permissions: buildAdminPermissions(roles),
      env: {
        name: (import.meta.env.MODE ?? "dev") as AdminMeResponse["env"]["name"],
        build: import.meta.env.VITE_BUILD_SHA ?? "unknown",
        region: import.meta.env.VITE_REGION ?? "local",
      },
      environment: {
        name: (import.meta.env.MODE ?? "dev") as AdminMeResponse["env"]["name"],
        build: import.meta.env.VITE_BUILD_SHA ?? "unknown",
        region: import.meta.env.VITE_REGION ?? "local",
      },
      read_only: false,
      audit_context: {
        require_reason: false,
        require_correlation_id: false,
      },
    };
  }

  const payload = isJson ? await parseJsonSafely<AdminErrorPayload>(response) : null;
  const inferredError =
    response.status === 401 ? "admin_unauthorized" : response.status === 403 ? "admin_forbidden" : "admin_error";
  const message = payload?.message ?? `Admin me failed with status ${response.status}`;
  throw new AdminMeError(response.status, message, {
    error: payload?.error ?? inferredError,
    message,
    status: response.status,
    request_id: payload?.request_id ?? requestId,
    required_roles: payload?.required_roles,
  });
}
