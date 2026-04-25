import type { ReactNode } from "react";
import { AppEmptyState } from "./states";
import { translate } from "../i18n";

type DemoEmptyStateProps = {
  title?: string;
  description?: ReactNode;
  action?: ReactNode;
};

export function DemoEmptyState({ title, description, action }: DemoEmptyStateProps) {
  return (
    <AppEmptyState
      title={title ?? translate("demoEmptyState.title")}
      description={description ?? translate("demoEmptyState.description")}
      action={action}
    />
  );
}
