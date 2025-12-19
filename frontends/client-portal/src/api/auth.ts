import { AUTH_API_BASE, request, UnauthorizedError, ValidationError } from "./http";
import type { AuthSession, LoginRequest, LoginResponse, MeResponse } from "./types";

export { UnauthorizedError, ValidationError };

export async function login(payload: LoginRequest): Promise<AuthSession> {
  const body = await request<LoginResponse>(
    "/auth/login",
    { method: "POST", body: JSON.stringify(payload) },
    undefined,
    AUTH_API_BASE,
  );
  return {
    token: body.access_token,
    email: body.email,
    roles: body.roles,
    subjectType: body.subject_type,
    clientId: body.client_id ?? undefined,
    expiresAt: Date.now() + body.expires_in * 1000,
  };
}

export async function fetchMe(token: string): Promise<MeResponse> {
  return request<MeResponse>("/auth/me", { method: "GET" }, token, AUTH_API_BASE);
}
