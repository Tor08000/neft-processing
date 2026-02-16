import { ApiError, request, requestWithMeta } from "./http";
import type { AuthSession } from "./types";

export type ClientOnboardingStatus =
  | "DRAFT"
  | "EMAIL_VERIFIED"
  | "ONBOARDING_PROFILE"
  | "ONBOARDING_DOCS"
  | "CONTRACT_READY"
  | "CONTRACT_SIGNED"
  | "ACTIVE"
  | "PENDING_ACTIVATION";

export interface OnboardingStatusResponse {
  client_id?: string | null;
  status: ClientOnboardingStatus;
  contract_status?: string | null;
  can_sign?: boolean;
}

export type ClientType = "LEGAL_ENTITY" | "SOLE_PROPRIETOR" | "INDIVIDUAL";

export interface OnboardingProfilePayload {
  client_type: ClientType;
  company_name: string;
  inn: string;
  kpp?: string | null;
  ogrn?: string | null;
  ogrnip?: string | null;
  legal_address: string;
  contact_person: {
    full_name: string;
    position: string;
    phone: string;
    email: string;
  };
}

export interface OnboardingContractInfo {
  pdf_url?: string | null;
  summary?: string | null;
}

export interface SignContractPayload {
  otp: string;
}

export interface OnboardingApplication {
  id: string;
  email: string;
  phone?: string | null;
  company_name?: string | null;
  inn?: string | null;
  ogrn?: string | null;
  org_type?: string | null;
  status: "DRAFT" | "SUBMITTED" | "IN_REVIEW" | "APPROVED" | "REJECTED";
  created_at: string;
  updated_at: string;
  submitted_at?: string | null;
}

export interface CreateApplicationPayload {
  email: string;
  phone?: string;
  company_name?: string;
  inn?: string;
  ogrn?: string;
  org_type?: string;
}

export interface CreateApplicationResponse {
  application: OnboardingApplication;
  access_token: string;
}

export type UpdateApplicationPayload = Partial<CreateApplicationPayload>;

const ONBOARDING_API_BASE = "/client/v1/onboarding";

export const ONBOARDING_APP_ID_KEY = "onboarding_app_id";
export const ONBOARDING_ACCESS_TOKEN_KEY = "onboarding_access_token";

export function saveOnboardingSession(applicationId: string, accessToken: string): void {
  localStorage.setItem(ONBOARDING_APP_ID_KEY, applicationId);
  localStorage.setItem(ONBOARDING_ACCESS_TOKEN_KEY, accessToken);
}

export function clearOnboardingSession(): void {
  localStorage.removeItem(ONBOARDING_APP_ID_KEY);
  localStorage.removeItem(ONBOARDING_ACCESS_TOKEN_KEY);
}

export function getOnboardingSession(): { appId: string | null; accessToken: string | null } {
  return {
    appId: localStorage.getItem(ONBOARDING_APP_ID_KEY),
    accessToken: localStorage.getItem(ONBOARDING_ACCESS_TOKEN_KEY),
  };
}

const withOnboardingAuth = (token: string): RequestInit => ({
  headers: { Authorization: `Bearer ${token}` },
});

export async function createApplication(payload: CreateApplicationPayload): Promise<CreateApplicationResponse> {
  return request<CreateApplicationResponse>(
    `${ONBOARDING_API_BASE}/applications`,
    { method: "POST", body: JSON.stringify(payload) },
    { base: "core", token: null },
  );
}

export function updateApplication(id: string, payload: UpdateApplicationPayload, token: string): Promise<OnboardingApplication> {
  return request<OnboardingApplication>(
    `${ONBOARDING_API_BASE}/applications/${id}`,
    { method: "PUT", body: JSON.stringify(payload), ...withOnboardingAuth(token) },
    { base: "core", token },
  );
}

export function submitApplication(id: string, token: string): Promise<OnboardingApplication> {
  return request<OnboardingApplication>(
    `${ONBOARDING_API_BASE}/applications/${id}/submit`,
    { method: "POST", ...withOnboardingAuth(token) },
    { base: "core", token },
  );
}

export function getApplication(id: string, token: string): Promise<OnboardingApplication> {
  return request<OnboardingApplication>(
    `${ONBOARDING_API_BASE}/applications/${id}`,
    { method: "GET", ...withOnboardingAuth(token) },
    { base: "core", token },
  );
}

export function getMyApplication(token: string): Promise<OnboardingApplication> {
  return request<OnboardingApplication>(
    `${ONBOARDING_API_BASE}/my-application`,
    { method: "GET", ...withOnboardingAuth(token) },
    { base: "core", token },
  );
}

export async function fetchOnboardingStatus(user: AuthSession | null): Promise<OnboardingStatusResponse | null> {
  try {
    return await request<OnboardingStatusResponse>(
      "/client/onboarding/status",
      { method: "GET" },
      { token: user?.token ?? undefined, base: "core" },
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export function submitOnboardingProfile(user: AuthSession | null, payload: OnboardingProfilePayload) {
  return requestWithMeta<OnboardingStatusResponse>(
    "/client/onboarding/profile",
    { method: "POST", body: JSON.stringify(payload) },
    { token: user?.token ?? undefined, base: "core" },
  );
}

export function uploadOnboardingFile(user: AuthSession | null, file: File, type: string) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("type", type);
  return requestWithMeta<{ status: string }>(
    "/client/onboarding/files",
    { method: "POST", body: formData },
    { token: user?.token ?? undefined, base: "core" },
  );
}

export function generateContract(user: AuthSession | null) {
  return requestWithMeta<OnboardingContractInfo>(
    "/client/onboarding/contract/generate",
    { method: "POST" },
    { token: user?.token ?? undefined, base: "core" },
  );
}

export function fetchContract(user: AuthSession | null) {
  return request<OnboardingContractInfo>(
    "/client/onboarding/contract",
    { method: "GET" },
    { token: user?.token ?? undefined, base: "core" },
  );
}

export function signContract(user: AuthSession | null, payload: SignContractPayload) {
  return requestWithMeta<OnboardingStatusResponse>(
    "/client/onboarding/contract/sign",
    { method: "POST", body: JSON.stringify(payload) },
    { token: user?.token ?? undefined, base: "core" },
  );
}
