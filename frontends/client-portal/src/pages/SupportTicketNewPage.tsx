import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createSupportTicket } from "../api/supportTickets";
import { useAuth } from "../auth/AuthContext";
import { AppErrorState } from "../components/states";
import type { SupportTicketPriority } from "../types/supportTickets";
import { supportTicketPriorityLabel } from "../utils/supportTickets";

const PRIORITY_OPTIONS: SupportTicketPriority[] = ["LOW", "NORMAL", "HIGH"];

export function SupportTicketNewPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [priority, setPriority] = useState<SupportTicketPriority>("NORMAL");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!user) {
    return <AppErrorState message="Требуется авторизация." />;
  }

  const handleSubmit = async () => {
    if (!subject || !message) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const ticket = await createSupportTicket({ subject, message, priority }, user);
      navigate(`/client/support/${ticket.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось создать обращение");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="card stack">
      <div>
        <h2>Создать обращение</h2>
        <p className="muted">Опишите проблему — мы ответим в ближайшее время.</p>
      </div>
      <label className="filter">
        Тема
        <input value={subject} onChange={(event) => setSubject(event.target.value)} />
      </label>
      <label className="filter">
        Описание
        <textarea rows={5} value={message} onChange={(event) => setMessage(event.target.value)} />
      </label>
      <label className="filter">
        Приоритет
        <select value={priority} onChange={(event) => setPriority(event.target.value as SupportTicketPriority)}>
          {PRIORITY_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {supportTicketPriorityLabel(option)}
            </option>
          ))}
        </select>
      </label>
      {error ? <div className="notice error">{error}</div> : null}
      <div className="actions">
        <button
          className="primary"
          type="button"
          onClick={() => void handleSubmit()}
          disabled={!subject || !message || isSubmitting}
        >
          Создать обращение
        </button>
        <button className="ghost" type="button" onClick={() => navigate("/client/support")}>
          Отмена
        </button>
      </div>
    </section>
  );
}
