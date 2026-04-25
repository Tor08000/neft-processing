import React, { useEffect, useMemo, useState } from "react";
import { CopyButton } from "../CopyButton/CopyButton";
import { createCorrelationId } from "../../utils/correlationId";

const DEBUG_ADMIN_WRITES = Boolean(import.meta.env.DEV && import.meta.env.VITE_ADMIN_DEBUG_WRITES === "true");

interface AdminWriteActionModalProps {
  isOpen: boolean;
  title?: string;
  confirmPhrase?: string;
  requirePhrase?: boolean;
  onConfirm: (payload: { reason: string; correlationId: string; requestId?: string }) => void;
  onCancel: () => void;
  requestId?: string;
}

export const AdminWriteActionModal: React.FC<AdminWriteActionModalProps> = ({
  isOpen,
  title = "Подтвердите действие",
  confirmPhrase = "CONFIRM",
  requirePhrase = false,
  onConfirm,
  onCancel,
  requestId,
}) => {
  const [reason, setReason] = useState("");
  const [typedPhrase, setTypedPhrase] = useState("");
  const [correlationId, setCorrelationId] = useState(() => createCorrelationId());

  useEffect(() => {
    if (!isOpen) return;
    setReason("");
    setTypedPhrase("");
    setCorrelationId(createCorrelationId());
  }, [isOpen]);

  const canConfirm = useMemo(() => {
    if (!reason.trim()) return false;
    if (!correlationId.trim()) return false;
    if (!requirePhrase) return true;
    return typedPhrase.trim().toUpperCase() === confirmPhrase;
  }, [reason, correlationId, typedPhrase, requirePhrase, confirmPhrase]);

  if (!isOpen) {
    return null;
  }

  const handleConfirm = () => {
    const trimmedReason = reason.trim();
    if (!trimmedReason) return;
    if (!correlationId.trim()) return;
    if (DEBUG_ADMIN_WRITES) {
      console.info("admin.write.attempt", {
        reason: trimmedReason,
        correlation_id: correlationId,
        request_id: requestId ?? null,
      });
    }
    onConfirm({ reason: trimmedReason, correlationId, requestId });
  };

  return (
    <div className="admin-modal__backdrop" role="dialog" aria-modal="true">
      <div className="admin-modal">
        <h2>{title}</h2>
        <label className="admin-modal__label" htmlFor="admin-write-reason">
          Причина (обязательное поле)
        </label>
        <textarea
          id="admin-write-reason"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder="Опишите причину действия"
          rows={3}
        />
        {requirePhrase && (
          <>
            <label className="admin-modal__label" htmlFor="admin-write-confirm">
              Введите {confirmPhrase} для подтверждения
            </label>
            <input
              id="admin-write-confirm"
              type="text"
              value={typedPhrase}
              onChange={(event) => setTypedPhrase(event.target.value)}
              placeholder={confirmPhrase}
            />
          </>
        )}
        {requestId && <div className="admin-modal__request">Request ID: {requestId}</div>}
        <label className="admin-modal__label" htmlFor="admin-write-correlation">
          Correlation ID (обязательное поле)
        </label>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            id="admin-write-correlation"
            type="text"
            value={correlationId}
            readOnly
            aria-readonly="true"
          />
          <CopyButton value={correlationId} label="Copy" />
          <button type="button" className="ghost" onClick={() => setCorrelationId(createCorrelationId())}>
            Regenerate
          </button>
        </div>
        <div className="admin-modal__actions">
          <button type="button" className="neft-btn-secondary" onClick={onCancel}>
            Отмена
          </button>
          <button type="button" className="neft-btn" onClick={handleConfirm} disabled={!canConfirm}>
            Подтвердить
          </button>
        </div>
      </div>
    </div>
  );
};

export default AdminWriteActionModal;
