import type { ReactNode } from "react";

export type DetailPanelProps = {
  open: boolean;
  title: ReactNode;
  subtitle?: ReactNode;
  onClose: () => void;
  closeLabel?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  headerActions?: ReactNode;
  size?: "md" | "lg" | "xl";
};

export function DetailPanel({
  open,
  title,
  subtitle,
  onClose,
  closeLabel = "Close",
  children,
  footer,
  headerActions,
  size = "lg",
}: DetailPanelProps) {
  if (!open) return null;

  return (
    <div className="detail-panel" role="dialog" aria-modal="true">
      <div className={`detail-panel__sheet detail-panel__sheet--${size}`}>
        <div className="detail-panel__header">
          <div className="detail-panel__titles">
            <h3 className="detail-panel__title">{title}</h3>
            {subtitle ? <div className="detail-panel__subtitle">{subtitle}</div> : null}
          </div>
          <div className="detail-panel__header-actions">
            {headerActions}
            <button type="button" className="ghost" onClick={onClose}>
              {closeLabel}
            </button>
          </div>
        </div>
        <div className="detail-panel__body">{children}</div>
        {footer ? <div className="detail-panel__footer">{footer}</div> : null}
      </div>
    </div>
  );
}

export default DetailPanel;
