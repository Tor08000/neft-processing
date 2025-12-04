import { request } from "./http";
import type { AuthSession, AuthUser, LoginRequest, LoginResponse, MeResponse } from "../types/auth";

export async function login(payload: LoginRequest): Promise<AuthSession> {
  const body = await request<LoginResponse>("/auth/login", { method: "POST", body: JSON.stringify(payload) });
  return {
    accessToken: body.access_token,
    expiresAt: Date.now() + body.expires_in * 1000,
    email: body.email,
    roles: body.roles,
  };
}

export async function me(token: string): Promise<AuthUser> {
  const body = await request<MeResponse>("/auth/me", { method: "GET" }, token);
  return {
    id: body.subject,
    email: body.email,
    roles: body.roles,
    subjectType: body.subject_type,
  };
}
