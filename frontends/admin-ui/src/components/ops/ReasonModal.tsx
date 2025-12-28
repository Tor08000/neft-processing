import React, { useEffect, useState } from "react";

interface ReasonModalProps {
  open: boolean;
  title: string;
  confirmLabel: string;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
}

export const ReasonModal: React.FC<ReasonModalProps> = ({ open, title, confirmLabel, onConfirm, onCancel }) => {
  const [reason, setReason] = useState("");

  useEffect(() => {
    if (open) {
      setReason("");
    }
  }, [open]);

  if (!open) return null;

  const canSubmit = reason.trim().length > 0;

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal">
        <h3 style={{ marginTop: 0 }}>{title}</h3>
        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span>Причина</span>
          <textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            rows={4}
            placeholder="Опишите причину"
            style={{ resize: "vertical" }}
          />
        </label>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
          <button type="button" className="ghost" onClick={onCancel}>
            Отмена
          </button>
          <button
            type="button"
            onClick={() => onConfirm(reason.trim())}
            disabled={!canSubmit}
            style={{
              padding: "8px 12px",
              borderRadius: 8,
              border: "none",
              background: canSubmit ? "#2563eb" : "#cbd5e1",
              color: "#fff",
              fontWeight: 600,
              cursor: canSubmit ? "pointer" : "not-allowed",
            }}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};
