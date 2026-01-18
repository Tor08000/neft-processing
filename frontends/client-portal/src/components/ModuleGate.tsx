import type { ReactNode } from "react";
import { ModuleUnavailablePage } from "../pages/ModuleUnavailablePage";
import { useClient } from "../auth/ClientContext";

type ModuleGateProps = {
  module?: string;
  capability?: string;
  title: string;
  children: ReactNode;
};

export function ModuleGate({ module, capability, title, children }: ModuleGateProps) {
  const { client } = useClient();
  const modulesPayload = client?.entitlements_snapshot?.modules as Record<string, { enabled?: boolean }> | undefined;
  const enabledModules = new Set(
    Object.entries(modulesPayload ?? {})
      .filter(([, payload]) => payload?.enabled)
      .map(([code]) => code.toUpperCase()),
  );
  const capabilities = new Set((client?.capabilities ?? []).map((code) => code.toUpperCase()));

  if ((module && !enabledModules.has(module)) || (capability && !capabilities.has(capability))) {
    return <ModuleUnavailablePage title={title} />;
  }

  return <>{children}</>;
}
