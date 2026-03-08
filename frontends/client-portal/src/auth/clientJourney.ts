import { AccessState } from "../access/accessState";
import type { PortalMeResponse } from "../api/clientPortal";

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
  | "ACTIVE"
  | "ERROR";

export type JourneyDraft = {
  selectedPlan?: string | null;
  customerType?: "INDIVIDUAL" | "SOLE_PROPRIETOR" | "LEGAL_ENTITY" | null;
  profileCompleted?: boolean;
  documentsGenerated?: boolean;
  documentsViewed?: boolean;
  documentsSigned?: boolean;
  paymentStatus?: "pending" | "processing" | "failed" | "succeeded";
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
  ACTIVE: "/dashboard",
  ERROR: "/dashboard",
};

export function resolveClientJourneyState(params: {
  authStatus: "loading" | "authenticated" | "unauthenticated";
  isDemo: boolean;
  client: PortalMeResponse | null;
  draft: JourneyDraft;
}): ClientJourneyState {
  const { authStatus, isDemo, client, draft } = params;
  if (authStatus !== "authenticated") return "ANON";
  if (isDemo) return "DEMO_SHOWCASE";

  if (client?.access_state === AccessState.ACTIVE || draft.paymentStatus === "succeeded") {
    return "ACTIVE";
  }

  if (!client?.org && !draft.selectedPlan && !draft.customerType && !draft.profileCompleted) {
    return "AUTHENTICATED_UNCONNECTED";
  }

  if (!draft.selectedPlan) return "NEEDS_PLAN";
  if (!draft.customerType) return "NEEDS_CUSTOMER_TYPE";
  if (!draft.profileCompleted) return "NEEDS_PROFILE";
  if (!draft.documentsGenerated || !draft.documentsViewed) return "NEEDS_DOCUMENTS";
  if (!draft.documentsSigned) return "NEEDS_SIGNATURE";
  if (draft.paymentStatus !== "pending" && draft.paymentStatus !== "processing") return "NEEDS_PAYMENT";

  return "NEEDS_PAYMENT";
}
