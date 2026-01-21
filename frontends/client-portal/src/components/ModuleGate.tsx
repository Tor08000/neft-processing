import type { ReactNode } from "react";
import { AccessGate } from "./AccessGate";

type ModuleGateProps = {
  module?: string;
  capability?: string;
  title: string;
  children: ReactNode;
};

export function ModuleGate({ module, capability, title, children }: ModuleGateProps) {
  return (
    <AccessGate module={module} capability={capability} title={title}>
      {children}
    </AccessGate>
  );
}
