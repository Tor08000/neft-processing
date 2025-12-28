import React, { useState } from "react";
import { MarkPayoutPayload } from "../../types/payouts";

interface MarkSentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (payload: MarkPayoutPayload) => void;
  isSubmitting?: boolean;
  error?: string | null;
}

export const MarkSentModal: React.FC<MarkSentModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  isSubmitting,
  error,
}) => {
  const [provider, setProvider] = useState("bank");
  const [externalRef, setExternalRef] = useState("");

  if (!isOpen) return null;

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    onConfirm({ provider, external_ref: externalRef });
  };

  return (
    <div className="modal-backdrop">
      <div className="modal">
        <h3>Mark batch as SENT</h3>
        <form onSubmit={handleSubmit} className="form-grid">
          <label>
            <span className="label">Provider</span>
            <select value={provider} onChange={(e) => setProvider(e.target.value)}>
              <option value="bank">bank</option>
              <option value="manual">manual</option>
              <option value="partner">partner</option>
            </select>
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
