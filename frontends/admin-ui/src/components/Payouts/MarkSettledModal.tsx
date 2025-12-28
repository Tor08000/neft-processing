import React, { useEffect, useState } from "react";
import { MarkPayoutPayload } from "../../types/payouts";

interface MarkSettledModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (payload: MarkPayoutPayload) => void;
  isSubmitting?: boolean;
  error?: string | null;
  defaultProvider?: string | null;
  defaultExternalRef?: string | null;
}

export const MarkSettledModal: React.FC<MarkSettledModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  isSubmitting,
  error,
  defaultProvider,
  defaultExternalRef,
}) => {
  const [provider, setProvider] = useState(defaultProvider ?? "bank");
  const [externalRef, setExternalRef] = useState(defaultExternalRef ?? "");

  useEffect(() => {
    if (isOpen) {
      setProvider(defaultProvider ?? "bank");
      setExternalRef(defaultExternalRef ?? "");
    }
  }, [defaultExternalRef, defaultProvider, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    onConfirm({ provider, external_ref: externalRef });
  };

  return (
    <div className="modal-backdrop">
      <div className="modal">
        <h3>Mark batch as SETTLED</h3>
        <form onSubmit={handleSubmit} className="form-grid">
          <label>
            <span className="label">Provider</span>
            <input value={provider} onChange={(e) => setProvider(e.target.value)} readOnly={Boolean(defaultProvider)} />
          </label>
          <label>
            <span className="label">External ref</span>
            <input value={externalRef} onChange={(e) => setExternalRef(e.target.value)} required />
          </label>
          {error && <div className="error-text">{error}</div>}
          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
            <button type="button" className="ghost" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="button primary" disabled={isSubmitting || !externalRef}>
              Confirm
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
