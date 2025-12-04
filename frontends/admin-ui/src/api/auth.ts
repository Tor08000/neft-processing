import { request } from "./http";
import type { AuthUser, LoginRequest, LoginResponse, MeResponse } from "../types/auth";

export async function login(payload: LoginRequest): Promise<AuthUser> {
  const body = await request<LoginResponse>("/auth/login", { method: "POST", body: JSON.stringify(payload) });
  return {
    token: body.access_token,
    email: body.email,
    roles: body.roles,
    subjectType: body.subject_type,
    expiresAt: Date.now() + body.expires_in * 1000,
  };
}

export async function me(token: string): Promise<AuthUser> {
  const body = await request<MeResponse>("/auth/me", { method: "GET" }, token);
  return {
    token,
    email: body.email,
    roles: body.roles,
    subjectType: body.subject_type,
    expiresAt: Date.now(),
  };
}
