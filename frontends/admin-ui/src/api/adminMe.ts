import { CORE_API_BASE } from "./base";
import type { AdminErrorPayload, AdminMeResponse } from "../types/admin";

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

export async function fetchAdminMe(token: string): Promise<AdminMeResponse> {
  const response = await fetch(buildUrl("/v1/admin/me"), {
    method: "GET",
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
  });

  const isJson = response.headers.get("content-type")?.includes("application/json");
  if (response.ok) {
    return (await response.json()) as AdminMeResponse;
  }

  const payload = isJson ? ((await response.json()) as AdminErrorPayload) : undefined;
  const message = payload?.message ?? `Admin me failed with status ${response.status}`;
  throw new AdminMeError(response.status, message, payload);
}
