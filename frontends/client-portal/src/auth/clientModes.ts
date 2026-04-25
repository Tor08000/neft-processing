import type { PortalMeResponse } from "../api/clientPortal";
import { getPlanByCode } from "@shared/subscriptions/catalog";
import type { ClientJourneyState } from "./clientJourney";
import { resolveClientKind } from "../access/clientWorkspace";

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

export const resolveAvailableClientModes = ({
  journeyState,
  client,
}: {
  journeyState: ClientJourneyState;
  client: PortalMeResponse | null;
}): ClientMode[] => {
  if (journeyState !== "ACTIVE" && journeyState !== "TRIAL_ACTIVE" && journeyState !== "DEMO_SHOWCASE") {
    return ["personal"];
  }

  if (journeyState === "DEMO_SHOWCASE") {
    return ["personal", "fleet"];
  }

  if (resolveClientKind({ client }) !== "BUSINESS") {
    return ["personal"];
  }

  const selectedPlan = getPlanByCode(client?.subscription?.plan_code ?? null);
  const modules = client?.modules;
  const entitlements = client?.entitlements_snapshot;
  const hasFleetByPlan = Boolean(selectedPlan?.modules.fleet || selectedPlan?.modules.logistics);
  const hasFleetByModules = hasEnabledModule(modules, "fleet") || hasEnabledModule(modules, "logistics");
  const hasFleetByEntitlements = hasEnabledModule(entitlements, "fleet") || hasEnabledModule(entitlements, "logistics");
  const hasFleetByCapabilities = (client?.capabilities ?? []).some((item) => FLEET_CAPABILITY_TOKENS.includes(item));
  const hasFleetBySection = (client?.nav_sections ?? []).some((item) => {
    const sectionCode = item.code.toLowerCase();
    return sectionCode.includes("fleet") || sectionCode.includes("logistics");
  });

  if (hasFleetByPlan || hasFleetByModules || hasFleetByEntitlements || hasFleetByCapabilities || hasFleetBySection) {
    return ["personal", "fleet"];
  }

  return ["personal"];
};

export const resolveActiveClientMode = (currentMode: ClientMode, availableModes: ClientMode[]): ClientMode =>
  availableModes.includes(currentMode) ? currentMode : availableModes[0] ?? "personal";
