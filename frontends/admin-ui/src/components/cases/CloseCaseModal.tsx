import React, { useEffect, useMemo, useState } from "react";
import type { CaseItem, CaseSnapshot } from "../../api/adminCases";

interface CloseCaseModalProps {
  open: boolean;
  caseItem?: CaseItem | null;
  selectedActionsCount?: number;
  onCancel: () => void;
  onSubmit: (payload: { resolutionNote: string; actionsApplied: boolean }) => Promise<void> | void;
}

const NOTE_MIN_LENGTH = 10;
const NOTE_MAX_LENGTH = 1000;

export const getSelectedActionsCount = (snapshot?: CaseSnapshot | null): number =>
  snapshot?.selected_actions?.length ?? 0;

export const CloseCaseModal: React.FC<CloseCaseModalProps> = ({
  open,
  caseItem,
  selectedActionsCount = 0,
  onCancel,
  onSubmit,
}) => {
  const [note, setNote] = useState("");
  const [actionsApplied, setActionsApplied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const validation = useMemo(() => {
    if (!note.trim()) return "Resolution note is required.";
    if (note.trim().length < NOTE_MIN_LENGTH) {
      return `Resolution note must be at least ${NOTE_MIN_LENGTH} characters.`;
    }
    if (note.trim().length > NOTE_MAX_LENGTH) {
      return `Resolution note must be under ${NOTE_MAX_LENGTH} characters.`;
    }
    return "";
  }, [note]);

  useEffect(() => {
    if (open) {
      setNote("");
      setActionsApplied(false);
      setError(null);
    }
  }, [open]);

  if (!open) return null;

  const handleSubmit = async () => {
    if (validation) {
      setError(validation);
      return;
    }
    setError(null);
    setIsSubmitting(true);
    try {
      await onSubmit({ resolutionNote: note.trim(), actionsApplied });
    } catch (submitError) {
      setError((submitError as Error).message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const showActionsApplied = selectedActionsCount > 0;

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal" style={{ maxWidth: 520 }}>
        <h3 style={{ marginTop: 0 }}>Close case {caseItem?.id}</h3>
        <div className="stack" style={{ gap: 12 }}>
          <label className="filter">
            Resolution note
            <textarea
              rows={4}
              value={note}
              onChange={(event) => setNote(event.target.value)}
              placeholder="Summary of how the case was resolved"
            />
            <div className="muted small">{note.length}/{NOTE_MAX_LENGTH}</div>
          </label>
          {showActionsApplied ? (
            <label className="stack-inline" style={{ alignItems: "center" }}>
              <input
                type="checkbox"
                checked={actionsApplied}
                onChange={(event) => setActionsApplied(event.target.checked)}
              />
              Actions were applied ({selectedActionsCount})
            </label>
          ) : null}
          {error ? <div className="error-state">{error}</div> : null}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <button type="button" className="ghost" onClick={onCancel} disabled={isSubmitting}>
              Cancel
            </button>
            <button
              type="button"
              className="neft-btn-primary"
              onClick={handleSubmit}
              disabled={Boolean(validation) || isSubmitting}
            >
              {isSubmitting ? "Closing..." : "Close case"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
