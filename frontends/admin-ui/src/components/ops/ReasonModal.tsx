import React, { useEffect, useState } from "react";

interface ReasonModalProps {
  open: boolean;
  title: string;
  confirmLabel: string;
  reasonOptions: { value: string; label?: string }[];
  onConfirm: (payload: { reasonCode: string; reasonText?: string }) => void;
  onCancel: () => void;
}

export const ReasonModal: React.FC<ReasonModalProps> = ({
  open,
  title,
  confirmLabel,
  reasonOptions,
  onConfirm,
  onCancel,
}) => {
  const [reasonCode, setReasonCode] = useState("");
  const [reasonText, setReasonText] = useState("");

  useEffect(() => {
    if (open) {
      setReasonCode(reasonOptions[0]?.value ?? "");
      setReasonText("");
    }
  }, [open, reasonOptions]);

  if (!open) return null;

  const requiresText = reasonCode.endsWith("_OTHER");
  const canSubmit = reasonCode && (!requiresText || reasonText.trim().length > 0);

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal">
        <h3 style={{ marginTop: 0 }}>{title}</h3>
        <label style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 12 }}>
          <span>Код причины</span>
          <select value={reasonCode} onChange={(event) => setReasonCode(event.target.value)}>
            {reasonOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label ?? option.value}
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span>Комментарий</span>
          <textarea
            value={reasonText}
            onChange={(event) => setReasonText(event.target.value)}
            rows={4}
            placeholder={requiresText ? "Опишите причину" : "Комментарий (опционально)"}
            style={{ resize: "vertical" }}
          />
        </label>
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
          <button type="button" className="ghost" onClick={onCancel}>
            Отмена
          </button>
          <button
            type="button"
            onClick={() => onConfirm({ reasonCode, reasonText: reasonText.trim() || undefined })}
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
