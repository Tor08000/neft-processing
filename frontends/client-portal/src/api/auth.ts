import { AUTH_API_BASE, request, ApiError, HtmlResponseError, UnauthorizedError, ValidationError } from "./http";
import type { AuthSession, LoginRequest, LoginResponse, MeResponse } from "./types";

export { ApiError, HtmlResponseError, UnauthorizedError, ValidationError };

const resolveToken = (body: LoginResponse | VerifyResponse): string => {
  const token = body.access_token ?? (body as LoginResponse & { token?: string }).token;
  if (!token) {
    throw new ApiError("Missing token in auth response", 500, null, null, "missing_token");
  }
  return token;
};

export async function login(payload: LoginRequest): Promise<AuthSession> {
  const body = await request<LoginResponse>(
    "/login",
    { method: "POST", body: JSON.stringify({ ...payload, portal: "client" }) },
    { base: "auth" },
  );
  return {
    token: resolveToken(body),
    email: body.email,
    roles: body.roles,
    subjectType: body.subject_type,
    clientId: body.client_id ?? undefined,
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
    "/me",
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
  access_token?: string;
  token?: string;
  token_type: string;
  expires_in: number;
  email: string;
  subject_type: string;
  client_id?: string | null;
  roles: string[];
}

export async function register(payload: RegisterPayload): Promise<RegisterResponse> {
  return request<RegisterResponse>("/register", { method: "POST", body: JSON.stringify(payload) }, { base: "auth" });
}

export async function verifyRegistration(payload: VerifyPayload): Promise<AuthSession> {
  const body = await request<VerifyResponse>(
    "/verify",
    { method: "POST", body: JSON.stringify(payload) },
    { base: "auth" },
  );
  return {
    token: resolveToken(body),
    email: body.email,
    roles: body.roles,
    subjectType: body.subject_type,
    clientId: body.client_id ?? undefined,
    expiresAt: Date.now() + body.expires_in * 1000,
  };
}
