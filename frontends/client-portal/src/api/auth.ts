import { AUTH_API_BASE, request, ApiError, HtmlResponseError, UnauthorizedError, ValidationError } from "./http";
import type { AuthSession, LoginRequest, LoginResponse, MeResponse } from "./types";

export { ApiError, HtmlResponseError, UnauthorizedError, ValidationError };

export async function login(payload: LoginRequest): Promise<AuthSession> {
  const body = await request<LoginResponse>(
    "/v1/auth/login",
    { method: "POST", body: JSON.stringify({ ...payload, portal: "client" }) },
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
  return request<MeResponse>(
    "/v1/auth/me",
    { method: "GET", headers: { "X-Portal": "client" } },
    { token, base: "auth" },
  );
}

export interface RegisterPayload {
  email?: string;
  phone?: string;
  password: string;
  consent_personal_data: boolean;
  consent_offer: boolean;
}

export interface RegisterResponse {
  verification_id: string;
  channel: "email" | "sms";
}

export interface VerifyPayload {
  verification_id: string;
  otp: string;
}

export interface VerifyResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  email: string;
  subject_type: string;
  client_id?: string | null;
  roles: string[];
}

export async function register(payload: RegisterPayload): Promise<RegisterResponse> {
  return request<RegisterResponse>("/v1/auth/register", { method: "POST", body: JSON.stringify(payload) }, { base: "auth" });
}

export async function verifyRegistration(payload: VerifyPayload): Promise<AuthSession> {
  const body = await request<VerifyResponse>(
    "/v1/auth/verify",
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
