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
    partnerId: body.partner_id ?? undefined,
    expiresAt: Date.now() + body.expires_in * 1000,
  };
}

export async function fetchMe(token: string): Promise<MeResponse> {
  if (import.meta.env.DEV) {
    const tokenPresent = Boolean(token);
    const headerAttached = tokenPresent;
    console.info("[auth-me] token_present=%s header_attached=%s", tokenPresent, headerAttached);
  }
  return request<MeResponse>(
    "/v1/auth/me",
    { method: "GET", headers: { "X-Portal": "partner" } },
    { token, base: "auth" },
  );
}
