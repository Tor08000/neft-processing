import type { ReactNode } from "react";
import { ModuleUnavailablePage } from "../pages/ModuleUnavailablePage";
import { useClient } from "../auth/ClientContext";

type ModuleGateProps = {
  module: string;
  title: string;
  children: ReactNode;
};

export function ModuleGate({ module, title, children }: ModuleGateProps) {
  const { client } = useClient();
  const enabledModules = new Set((client?.entitlements.enabled_modules ?? []).map((code) => code.toUpperCase()));

  if (!enabledModules.has(module)) {
    return <ModuleUnavailablePage title={title} />;
  }

  return <>{children}</>;
}
