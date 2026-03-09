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

export type JourneyDraft = {
  selectedPlan?: string | null;
  customerType?: CustomerType | null;
  profileCompleted?: boolean;
  documentsGenerated?: boolean;
  documentsViewed?: boolean;
  documentsSigned?: boolean;
  subscriptionState?: SubscriptionState;
};

export const JOURNEY_ROUTE_BY_STATE: Record<ClientJourneyState, string> = {
  ANON: "/login",
  DEMO_SHOWCASE: "/dashboard",
  AUTHENTICATED_UNCONNECTED: "/connect",
  NEEDS_PLAN: "/connect/plan",
  NEEDS_CUSTOMER_TYPE: "/connect/type",
  NEEDS_PROFILE: "/connect/profile",
  NEEDS_DOCUMENTS: "/connect/documents",
  NEEDS_SIGNATURE: "/connect/sign",
  NEEDS_PAYMENT: "/connect/payment",
  TRIAL_ACTIVE: "/dashboard",
  ACTIVE: "/dashboard",
  ERROR: "/dashboard",
};

const isPaidPending = (s?: SubscriptionState) => s === "PAYMENT_PENDING" || s === "PAYMENT_PROCESSING";

export function resolveClientJourneyState(params: {
  authStatus: "loading" | "authenticated" | "unauthenticated";
  isDemo: boolean;
  client: PortalMeResponse | null;
  draft: JourneyDraft;
}): ClientJourneyState {
  const { authStatus, isDemo, client, draft } = params;
  if (authStatus !== "authenticated") return "ANON";
  if (isDemo) return "DEMO_SHOWCASE";

  if (client?.access_state === AccessState.ACTIVE || draft.subscriptionState === "ACTIVE") return "ACTIVE";
  if (draft.subscriptionState === "TRIAL_ACTIVE") return "TRIAL_ACTIVE";

  if (!client?.org && !draft.selectedPlan && !draft.customerType && !draft.profileCompleted) return "AUTHENTICATED_UNCONNECTED";
  if (!draft.selectedPlan) return "NEEDS_PLAN";
  if (!draft.customerType) return "NEEDS_CUSTOMER_TYPE";
  if (!draft.profileCompleted) return "NEEDS_PROFILE";
  if (!draft.documentsGenerated || !draft.documentsViewed) return "NEEDS_DOCUMENTS";
  if (!draft.documentsSigned) return "NEEDS_SIGNATURE";
  if (draft.selectedPlan === "CLIENT_FREE_TRIAL") return "TRIAL_ACTIVE";
  if (!isPaidPending(draft.subscriptionState)) return "NEEDS_PAYMENT";
  return "NEEDS_PAYMENT";
}
