import type { PortalMeResponse } from "../api/clientPortal";
import { getPlanByCode, type CustomerType } from "@shared/subscriptions/catalog";
import type { ClientJourneyState, JourneyDraft } from "./clientJourney";

export type ClientMode = "personal" | "fleet";

const FLEET_CAPABILITY_TOKENS = ["FLEET", "LOGISTICS", "CLIENT_FLEET", "CLIENT_LOGISTICS"];

const hasEnabledModule = (modules: unknown, key: string): boolean => {
  if (!modules || typeof modules !== "object") return false;
  const value = (modules as Record<string, unknown>)[key];
  if (typeof value === "boolean") return value;
  if (value && typeof value === "object" && "enabled" in value) {
    return Boolean((value as Record<string, unknown>).enabled);
  }
  return false;
};

const hasFleetSignalsFromCustomerType = (customerType?: CustomerType | null): boolean =>
  customerType === "LEGAL_ENTITY" || customerType === "SOLE_PROPRIETOR";

export const resolveAvailableClientModes = ({
  journeyState,
  draft,
  client,
}: {
  journeyState: ClientJourneyState;
  draft: JourneyDraft;
  client: PortalMeResponse | null;
}): ClientMode[] => {
  if (journeyState !== "ACTIVE" && journeyState !== "TRIAL_ACTIVE" && journeyState !== "DEMO_SHOWCASE") {
    return ["personal"];
  }

  if (journeyState === "DEMO_SHOWCASE") {
    return ["personal", "fleet"];
  }

  const selectedPlan = getPlanByCode(draft.selectedPlan ?? client?.subscription?.plan_code ?? null);
  const modules = client?.modules;
  const entitlements = client?.entitlements_snapshot;
  const hasFleetByPlan = Boolean(selectedPlan?.modules.fleet || selectedPlan?.modules.logistics);
  const hasFleetByModules = hasEnabledModule(modules, "fleet") || hasEnabledModule(modules, "logistics");
  const hasFleetByEntitlements = hasEnabledModule(entitlements, "fleet") || hasEnabledModule(entitlements, "logistics");
  const hasFleetByCapabilities = (client?.capabilities ?? []).some((item) => FLEET_CAPABILITY_TOKENS.includes(item));
  const hasFleetBySection = (client?.nav_sections ?? []).some((item) => item.code.toLowerCase().includes("fleet"));
  const hasFleetByCustomer = hasFleetSignalsFromCustomerType(draft.customerType);

  if (hasFleetByPlan || hasFleetByModules || hasFleetByEntitlements || hasFleetByCapabilities || hasFleetBySection || hasFleetByCustomer) {
    return ["personal", "fleet"];
  }

  return ["personal"];
};

export const resolveActiveClientMode = (currentMode: ClientMode, availableModes: ClientMode[]): ClientMode =>
  availableModes.includes(currentMode) ? currentMode : availableModes[0] ?? "personal";

