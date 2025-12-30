import type { ReactNode } from "react";

type ConfirmActionModalProps = {
  isOpen: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  isProcessing?: boolean;
  isConfirmDisabled?: boolean;
  children?: ReactNode;
  footerNote?: ReactNode;
};

export function ConfirmActionModal({
  isOpen,
  title,
  description,
  confirmLabel = "Подтвердить",
  cancelLabel = "Отмена",
  onConfirm,
  onCancel,
  isProcessing = false,
  isConfirmDisabled = false,
  children,
  footerNote,
}: ConfirmActionModalProps) {
  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal-card">
        <div className="card__header">
          <div>
            <h3>{title}</h3>
            {description ? <p className="muted">{description}</p> : null}
          </div>
          <button type="button" className="ghost" onClick={onCancel}>
            Закрыть
          </button>
        </div>
        <div className="stack">
          {children}
          {footerNote ? <div className="muted small">{footerNote}</div> : null}
          <div className="actions">
            <button
              type="button"
              className="primary"
              onClick={onConfirm}
              disabled={isConfirmDisabled || isProcessing}
            >
              {confirmLabel}
            </button>
            <button type="button" className="ghost" onClick={onCancel}>
              {cancelLabel}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
