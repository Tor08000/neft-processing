import { AccessState } from "../access/accessState";
import type { PortalMeResponse } from "../api/clientPortal";
import type { CustomerType, SubscriptionState } from "@shared/subscriptions/catalog";

export type ClientJourneyState =
  | "ANON"
  | "DEMO_SHOWCASE"
  | "AUTHENTICATED_UNCONNECTED"
  | "NEEDS_PLAN"
  | "NEEDS_CUSTOMER_TYPE"
  | "NEEDS_PROFILE"
  | "NEEDS_DOCUMENTS"
  | "NEEDS_SIGNATURE"
  | "NEEDS_PAYMENT"
  | "TRIAL_ACTIVE"
  | "ACTIVE"
  | "ERROR";

export type DocumentStatus = "pending_generation" | "ready" | "reviewed";

export type JourneyDraft = {
  selectedPlan?: string | null;
  customerType?: CustomerType | null;
  profileCompleted?: boolean;
  documentsGenerated?: boolean;
  documentsViewed?: boolean;
  documentsSigned?: boolean;
  subscriptionState?: SubscriptionState;
  profileData?: Partial<Record<"fullName"|"legalName"|"phone"|"email"|"inn"|"kpp"|"ogrn"|"ogrnip"|"address"|"contact", string>>;
  signAccepted?: boolean;
  signAcceptedAt?: string;
  signatureState?: "signPending" | "signAccepted";
  documentsByCode?: Record<string, DocumentStatus>;
};

export const JOURNEY_ROUTE_BY_STATE: Record<ClientJourneyState, string> = {
  ANON: "/login",
  DEMO_SHOWCASE: "/dashboard",
  AUTHENTICATED_UNCONNECTED: "/onboarding",
  NEEDS_PLAN: "/onboarding/plan",
  NEEDS_CUSTOMER_TYPE: "/onboarding",
  NEEDS_PROFILE: "/onboarding",
  NEEDS_DOCUMENTS: "/onboarding/contract",
  NEEDS_SIGNATURE: "/onboarding/contract",
  NEEDS_PAYMENT: "/onboarding/contract",
  TRIAL_ACTIVE: "/dashboard",
  ACTIVE: "/dashboard",
  ERROR: "/dashboard",
};

const hasReviewedDocuments = (draft: JourneyDraft): boolean => {
  if (draft.documentsByCode) {
    return Object.values(draft.documentsByCode).length > 0 && Object.values(draft.documentsByCode).every((status) => status === "reviewed");
  }
  return Boolean(draft.documentsGenerated && draft.documentsViewed);
};

const isPaymentCompleted = (state?: SubscriptionState) => state === "ACTIVE";

export function resolveClientJourneyState(params: {
  authStatus: "loading" | "authenticated" | "unauthenticated";
  isDemo: boolean;
  client: PortalMeResponse | null;
  draft: JourneyDraft;
}): ClientJourneyState {
  const { authStatus, isDemo, client, draft } = params;
  if (authStatus !== "authenticated") return "ANON";
  if (isDemo) return "DEMO_SHOWCASE";

  if (client?.access_state === AccessState.ACTIVE || isPaymentCompleted(draft.subscriptionState)) return "ACTIVE";
  if (draft.subscriptionState === "TRIAL_ACTIVE") return "TRIAL_ACTIVE";
  if (client?.access_state === AccessState.NEEDS_CONTRACT) return "NEEDS_SIGNATURE";
  if (client?.access_state === AccessState.NEEDS_PLAN) return "NEEDS_PLAN";
  if (client?.access_state === AccessState.NEEDS_ONBOARDING && client?.org) return "NEEDS_PROFILE";

  if (!client?.org && !draft.selectedPlan && !draft.customerType && !draft.profileCompleted) return "AUTHENTICATED_UNCONNECTED";
  if (!draft.selectedPlan) return "NEEDS_PLAN";
  if (!draft.customerType) return "NEEDS_CUSTOMER_TYPE";
  if (!draft.profileCompleted) return "NEEDS_PROFILE";
  if (!hasReviewedDocuments(draft)) return "NEEDS_DOCUMENTS";

  const hasAcceptedSignature = Boolean(draft.signAccepted && draft.documentsSigned);
  if (!hasAcceptedSignature) return "NEEDS_SIGNATURE";

  if (draft.selectedPlan === "CLIENT_FREE_TRIAL") return "TRIAL_ACTIVE";

  if (draft.subscriptionState === "PAYMENT_PENDING" || draft.subscriptionState === "PAYMENT_PROCESSING" || draft.subscriptionState === "PAYMENT_FAILED") {
    return "NEEDS_PAYMENT";
  }

  return "NEEDS_PAYMENT";
}
