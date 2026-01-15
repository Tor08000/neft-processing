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
