import { AUTH_API_BASE, request, ApiError, HtmlResponseError, UnauthorizedError, ValidationError } from "./http";
import type { AuthSession, LoginRequest, LoginResponse, MeResponse } from "./types";

export { ApiError, HtmlResponseError, UnauthorizedError, ValidationError };

export async function login(payload: LoginRequest): Promise<AuthSession> {
  const body = await request<LoginResponse>(
    "/v1/auth/login",
    { method: "POST", body: JSON.stringify(payload) },
    { base: "auth" },
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
  return request<MeResponse>("/v1/auth/me", { method: "GET" }, { token, base: "auth" });
}
