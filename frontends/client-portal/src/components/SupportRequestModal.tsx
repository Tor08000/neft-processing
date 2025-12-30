import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { createSupportRequest } from "../api/support";
import { useAuth } from "../auth/AuthContext";
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
          scope_type: "CLIENT",
          subject_type: subjectType,
          subject_id: subjectId ?? null,
          title,
          description,
          correlation_id: correlationId ?? undefined,
          event_id: eventId ?? undefined,
        },
        user,
      );
      setResult(created);
      setDescription("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось отправить обращение");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal-card">
        <div className="card__header">
          <div>
            <h3>Создать обращение</h3>
            <p className="muted">Мы получим ваш запрос и свяжемся после проверки.</p>
          </div>
          <button type="button" className="ghost" onClick={onClose}>
            Закрыть
          </button>
        </div>
        {result ? (
          <div className="stack">
            <div className="notice">
              <strong>Обращение создано</strong>
              <div className="muted small">Номер обращения: {result.id}</div>
              {result.correlation_id ? (
                <div className="muted small">Correlation ID: {result.correlation_id}</div>
              ) : null}
            </div>
            <Link className="link-button" to={`/support/requests/${result.id}`} onClick={onClose}>
              Перейти к обращению
            </Link>
          </div>
        ) : (
          <div className="stack">
            <label className="filter">
              Тема
              <input value={title} onChange={(event) => setTitle(event.target.value)} />
            </label>
            <label className="filter">
              Описание
              <textarea rows={4} value={description} onChange={(event) => setDescription(event.target.value)} />
            </label>
            {error ? <div className="notice error">{error}</div> : null}
            <div className="actions">
              <button type="button" className="primary" onClick={() => void handleSubmit()} disabled={!title || !description || isSubmitting}>
                Отправить
              </button>
              <button type="button" className="ghost" onClick={onClose}>
                Отмена
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
