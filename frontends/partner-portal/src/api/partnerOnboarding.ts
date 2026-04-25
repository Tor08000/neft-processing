import { request } from "./http";

export interface PartnerOnboardingSnapshot {
  partner: {
    id: string;
    code: string;
    legal_name: string;
    brand_name?: string | null;
    partner_type: string;
    status: string;
    contacts?: Record<string, unknown>;
  };
  checklist: {
    profile_complete: boolean;
    legal_documents_accepted: boolean;
    legal_profile_present: boolean;
    legal_details_present: boolean;
    legal_details_complete: boolean;
    legal_verified: boolean;
    activation_ready: boolean;
    blocked_reasons: string[];
    next_step: string;
    next_route: string;
  };
}

export const fetchPartnerOnboarding = (token: string) =>
  request<PartnerOnboardingSnapshot>("/partner/onboarding", { method: "GET" }, { token, base: "core_root" });

export const patchPartnerOnboardingProfile = (
  token: string,
  payload: { brand_name?: string; contacts?: Record<string, unknown> },
) =>
  request<PartnerOnboardingSnapshot["partner"]>(
    "/partner/onboarding/profile",
    { method: "PATCH", body: JSON.stringify(payload) },
    { token, base: "core_root" },
  );

export const activatePartnerOnboarding = (token: string) =>
  request<PartnerOnboardingSnapshot>("/partner/onboarding/activate", { method: "POST" }, { token, base: "core_root" });
