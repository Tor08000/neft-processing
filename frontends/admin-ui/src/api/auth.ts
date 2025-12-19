import { request } from "./http";
import type { AuthSession, AuthUser, LoginRequest, LoginResponse, MeResponse } from "../types/auth";

export async function login(payload: LoginRequest): Promise<AuthSession> {
  const body = await request<LoginResponse>(
    "/api/v1/auth/login",
    { method: "POST", body: JSON.stringify(payload) },
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
  const body = await request<MeResponse>("/api/v1/auth/me", { method: "GET" }, { token, base: "auth" });
  return {
    id: body.subject,
    email: body.email,
    roles: body.roles,
    subjectType: body.subject_type,
  };
}
