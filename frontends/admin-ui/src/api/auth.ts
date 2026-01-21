import { request } from "./http";
import type { AuthSession, AuthUser, LoginRequest, LoginResponse, MeResponse } from "../types/auth";

export async function login(payload: LoginRequest): Promise<AuthSession> {
  const body = await request<LoginResponse>(
    "/v1/auth/login",
    { method: "POST", body: JSON.stringify({ ...payload, portal: "admin" }) },
    { base: "auth" },
  );
  return {
    accessToken: body.access_token,
    expiresAt: Date.now() + body.expires_in * 1000,
    email: body.email,
    roles: body.roles,
  };
}

export async function me(token: string): Promise<AuthUser> {
  if (import.meta.env.DEV) {
    const tokenPresent = Boolean(token);
    const headerAttached = tokenPresent;
    console.info("[auth-me] token_present=%s header_attached=%s", tokenPresent, headerAttached);
  }
  const body = await request<MeResponse>(
    "/v1/auth/me",
    { method: "GET", headers: { "X-Portal": "admin" } },
    { token, base: "auth" },
  );
  return {
    id: body.subject,
    email: body.email,
    roles: body.roles,
    subjectType: body.subject_type,
  };
}
