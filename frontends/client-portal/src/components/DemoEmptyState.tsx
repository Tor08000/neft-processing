import type { ReactNode } from "react";
import { AppEmptyState } from "./states";

type DemoEmptyStateProps = {
  title?: string;
  description?: ReactNode;
  action?: ReactNode;
};

export function DemoEmptyState({ title, description, action }: DemoEmptyStateProps) {
  return (
    <AppEmptyState
      title={title ?? "Раздел в демо недоступен"}
      description={description ?? "В рабочем контуре здесь будут доступны все данные и сценарии."}
      action={action}
    />
  );
}
