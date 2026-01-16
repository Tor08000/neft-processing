import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { createSupportTicket } from "../api/supportTickets";
import { useAuth } from "../auth/AuthContext";
import type { SupportTicketDetail, SupportTicketPriority } from "../types/supportTickets";
import { supportTicketPriorityLabel } from "../utils/supportTickets";

type SupportRequestModalProps = {
  isOpen: boolean;
  onClose: () => void;
  defaultSubject: string;
};

export function SupportRequestModal({
  isOpen,
  onClose,
  defaultSubject,
}: SupportRequestModalProps) {
  const { user } = useAuth();
  const [subject, setSubject] = useState(defaultSubject);
  const [message, setMessage] = useState("");
  const [priority, setPriority] = useState<SupportTicketPriority>("NORMAL");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SupportTicketDetail | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    setSubject(defaultSubject);
    setMessage("");
    setPriority("NORMAL");
    setError(null);
    setResult(null);
  }, [defaultSubject, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async () => {
    if (!user) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const created = await createSupportTicket({ subject, message, priority }, user);
      setResult(created);
      setMessage("");
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
            </div>
            <Link className="link-button" to={`/client/support/${result.id}`} onClick={onClose}>
              Перейти к обращению
            </Link>
          </div>
        ) : (
          <div className="stack">
            <label className="filter">
              Тема
              <input value={subject} onChange={(event) => setSubject(event.target.value)} />
            </label>
            <label className="filter">
              Описание
              <textarea rows={4} value={message} onChange={(event) => setMessage(event.target.value)} />
            </label>
            <label className="filter">
              Приоритет
              <select value={priority} onChange={(event) => setPriority(event.target.value as SupportTicketPriority)}>
                {["LOW", "NORMAL", "HIGH"].map((option) => (
                  <option key={option} value={option}>
                    {supportTicketPriorityLabel(option as SupportTicketPriority)}
                  </option>
                ))}
              </select>
            </label>
            {error ? <div className="notice error">{error}</div> : null}
            <div className="actions">
              <button
                type="button"
                className="primary"
                onClick={() => void handleSubmit()}
                disabled={!subject || !message || isSubmitting}
              >
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
