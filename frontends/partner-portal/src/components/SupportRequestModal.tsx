import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { createSupportRequest } from "../api/support";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import type { SupportRequestDetail, SupportRequestSubjectType } from "../types/support";

type SupportRequestModalProps = {
  isOpen: boolean;
  onClose: () => void;
  subjectType: SupportRequestSubjectType;
  subjectId?: string | null;
  correlationId?: string | null;
  eventId?: string | null;
  defaultTitle: string;
};

export function SupportRequestModal({
  isOpen,
  onClose,
  subjectType,
  subjectId,
  correlationId,
  eventId,
  defaultTitle,
}: SupportRequestModalProps) {
  const { user } = useAuth();
  const { t } = useI18n();
  const [title, setTitle] = useState(defaultTitle);
  const [description, setDescription] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SupportRequestDetail | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    setTitle(defaultTitle);
    setDescription("");
    setError(null);
    setResult(null);
  }, [defaultTitle, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async () => {
    if (!user) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const created = await createSupportRequest(
        {
          scope_type: "PARTNER",
          subject_type: subjectType,
          subject_id: subjectId ?? null,
          title,
          description,
          correlation_id: correlationId ?? undefined,
          event_id: eventId ?? undefined,
        },
        user.token,
      );
      setResult(created);
      setDescription("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("supportRequests.errors.createFailed"));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal">
        <div className="card__header">
          <div>
            <h3>{t("supportRequests.modal.title")}</h3>
            <p className="muted">{t("supportRequests.modal.subtitle")}</p>
          </div>
          <button type="button" className="ghost" onClick={onClose}>
            {t("actions.close")}
          </button>
        </div>
        {result ? (
          <div className="stack">
            <div className="notice">
              <strong>{t("supportRequests.modal.createdTitle")}</strong>
            </div>
            <Link className="link-button" to={`/support/requests/${result.id}`} onClick={onClose}>
              {t("supportRequests.modal.openRequest")}
            </Link>
          </div>
        ) : (
          <div className="stack">
            <label className="filter">
              {t("supportRequests.fields.title")}
              <input value={title} onChange={(event) => setTitle(event.target.value)} />
            </label>
            <label className="filter">
              {t("supportRequests.fields.description")}
              <textarea rows={4} value={description} onChange={(event) => setDescription(event.target.value)} />
            </label>
            {error ? <div className="notice error">{error}</div> : null}
            <div className="actions">
              <button
                type="button"
                className="primary"
                onClick={() => void handleSubmit()}
                disabled={!title || !description || isSubmitting}
              >
                {t("supportRequests.actions.submit")}
              </button>
              <button type="button" className="ghost" onClick={onClose}>
                {t("actions.cancel")}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
