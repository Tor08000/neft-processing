import { EmptyState } from "./EmptyState";

type DemoEmptyStateAction = {
  label: string;
  onClick?: () => void;
  to?: string;
  href?: string;
  variant?: "primary" | "secondary" | "ghost";
};

type DemoEmptyStateProps = {
  title?: string;
  description?: string;
  primaryAction?: DemoEmptyStateAction;
  secondaryAction?: DemoEmptyStateAction;
};

export function DemoEmptyState({
  title = "Раздел доступен в рабочем контуре",
  description = "В демо-режиме данные ограничены. В рабочем контуре здесь отображаются реальные показатели и документы.",
  primaryAction,
  secondaryAction,
}: DemoEmptyStateProps) {
  return (
    <EmptyState
      title={title}
      description={description}
      primaryAction={primaryAction}
      secondaryAction={secondaryAction}
      actionsClassName="neft-empty-actions"
    />
  );
}
