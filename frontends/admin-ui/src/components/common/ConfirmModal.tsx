import React from "react";

interface ConfirmModalProps {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmModal: React.FC<ConfirmModalProps> = ({
  open,
  title,
  description,
  confirmLabel = "Подтвердить",
  cancelLabel = "Отмена",
  danger,
  onConfirm,
  onCancel,
}) => {
  if (!open) return null;

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal">
        <h3 style={{ marginTop: 0 }}>{title}</h3>
        {description && <p style={{ color: "#475569" }}>{description}</p>}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
          <button type="button" className="ghost" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            style={{
              padding: "8px 12px",
              borderRadius: 8,
              border: "none",
              background: danger ? "#dc2626" : "#2563eb",
              color: "#fff",
              fontWeight: 600,
            }}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};
