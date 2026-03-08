import { AUTH_API_BASE, request, ApiError, HtmlResponseError, UnauthorizedError, ValidationError } from "./http";
import type { AuthSession, LoginRequest, LoginResponse, MeResponse } from "./types";

export { ApiError, HtmlResponseError, UnauthorizedError, ValidationError };

const resolveToken = (body: LoginResponse): string => {
  const token = body.access_token ?? (body as LoginResponse & { token?: string }).token;
  if (!token) {
    throw new ApiError("Missing token in auth response", 500, null, null, "missing_token");
  }
  return token;
};

export async function login(payload: LoginRequest): Promise<AuthSession> {
  const body = await request<LoginResponse>(
    "/login",
    { method: "POST", body: JSON.stringify(payload) },
    { base: "auth" },
  );
  return {
    token: resolveToken(body),
    refreshToken: body.refresh_token,
    email: body.email,
    roles: body.roles,
    subjectType: body.subject_type,
    clientId: body.client_id ?? undefined,
    expiresAt: Date.now() + body.expires_in * 1000,
  };
}

export async function fetchMe(token: string): Promise<MeResponse> {
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
  consent?: boolean;
  portal?: string;
}

export interface RegisterResponse {
  id: string;
  email: string;
  full_name?: string | null;
  is_active: boolean;
  created_at?: string | null;
  access_token?: string;
  token_type?: string;
  expires_in?: number;
  subject_type?: string;
  client_id?: string | null;
  roles?: string[];
}

export async function register(payload: RegisterPayload): Promise<RegisterResponse> {
  const consentValue = payload.consent ?? (payload.consent_personal_data && payload.consent_offer);
  const normalizedPayload = {
    ...payload,
    portal: payload.portal ?? "client",
    ...(consentValue !== undefined ? { consent: consentValue } : {}),
  };
  return request<RegisterResponse>("/signup", { method: "POST", body: JSON.stringify(normalizedPayload) }, { base: "auth", token: null });
}


export interface SSOIdPItem {
  provider_key: string;
  display_name: string;
  issuer_url: string;
  enabled: boolean;
}

export interface SSOIdPListResponse {
  tenant_id: string;
  portal: string;
  idps: SSOIdPItem[];
}

export async function listSsoIdps(tenantId: string): Promise<SSOIdPListResponse> {
  return request<SSOIdPListResponse>(`/sso/idps?tenant_id=${encodeURIComponent(tenantId)}&portal=client`, { method: "GET" }, { base: "auth" });
}

export function buildSsoStartUrl(tenantId: string, providerKey: string, redirectUri: string): string {
  return `${AUTH_API_BASE}/sso/oidc/start?tenant_id=${encodeURIComponent(tenantId)}&provider_key=${encodeURIComponent(providerKey)}&portal=client&redirect_uri=${encodeURIComponent(redirectUri)}`;
}
