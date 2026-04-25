import React from "react";
import { EmptyState as BrandEmptyState } from "@shared/brand/components";

interface EmptyStateProps {
  title: string;
  description?: string;
  hint?: string;
  icon?: React.ReactNode;
  primaryAction?: {
    label: string;
    onClick?: () => void;
  };
  secondaryAction?: {
    label: string;
    onClick?: () => void;
  };
  actionLabel?: string;
  actionOnClick?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  hint,
  icon,
  primaryAction,
  secondaryAction,
  actionLabel,
  actionOnClick,
}) => (
  <BrandEmptyState
    title={title}
    description={description}
    hint={hint}
    icon={icon}
    primaryAction={primaryAction ?? (actionLabel ? { label: actionLabel, onClick: actionOnClick } : undefined)}
    secondaryAction={secondaryAction}
  />
);
