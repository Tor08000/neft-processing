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
  title = "Данных пока нет",
  description = "В демо-режиме показан примерный набор данных.",
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
