import type { ReactNode } from "react";
import { AppLogo } from "./AppLogo";

export type EmptyStateProps = {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
};

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <AppLogo size={48} className="empty-state__logo" />
      <h2 className="empty-state__title">{title}</h2>
      {description ? <p className="empty-state__description">{description}</p> : null}
      {action ? <div className="empty-state__action">{action}</div> : null}
    </div>
  );
}

export default EmptyState;
