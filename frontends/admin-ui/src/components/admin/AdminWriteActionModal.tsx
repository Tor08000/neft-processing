import React, { useMemo, useState } from "react";

interface AdminWriteActionModalProps {
  isOpen: boolean;
  title?: string;
  confirmPhrase?: string;
  requirePhrase?: boolean;
  onConfirm: (payload: { reason: string; requestId?: string }) => void;
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

  const canConfirm = useMemo(() => {
    if (!reason.trim()) return false;
    if (!requirePhrase) return true;
    return typedPhrase.trim().toUpperCase() === confirmPhrase;
  }, [reason, typedPhrase, requirePhrase, confirmPhrase]);

  if (!isOpen) {
    return null;
  }

  const handleConfirm = () => {
    const trimmedReason = reason.trim();
    if (!trimmedReason) return;
    console.info("admin.write.attempt", {
      reason: trimmedReason,
      request_id: requestId ?? null,
    });
    onConfirm({ reason: trimmedReason, requestId });
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
