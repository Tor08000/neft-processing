import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { createSupportTicket } from "../api/supportTickets";
import { useAuth } from "../auth/AuthContext";
import { AppEmptyState, AppErrorState } from "../components/states";
import type { SupportTicketPriority } from "../types/supportTickets";
import { supportTicketPriorityLabel } from "../utils/supportTickets";

const PRIORITY_OPTIONS: SupportTicketPriority[] = ["LOW", "NORMAL", "HIGH"];

const TOPIC_PRESETS: Record<
  string,
  { subject: string; message: string; description: string }
> = {
  billing: {
    subject: "Вопрос по оплате или задолженности",
    message: "Опишите, какой счёт, выгрузка или платёж требуют проверки.",
    description: "Контур финансов и сверки.",
  },
  plan: {
    subject: "Вопрос по возможностям тарифа",
    message: "Укажите, какой доступ или сценарий нужно открыть.",
    description: "Контур тарифов и доступов.",
  },
  payout: {
    subject: "Вопрос по выплате",
    message: "Опишите, какая выплата или экспорт требуют проверки.",
    description: "Контур выплат и расчётов.",
  },
  sla: {
    subject: "Вопрос по SLA или срокам",
    message: "Опишите, в каком процессе сроки выглядят неверно.",
    description: "Контур сроков и обязательств.",
  },
  document_signature: {
    subject: "Проблема с подписанием документа",
    message: "Опишите документ, шаг подписания и что именно не удалось выполнить.",
    description: "Контур подписи документов.",
  },
  document_edo: {
    subject: "Проблема с ЭДО",
    message: "Опишите документ и шаг обмена, на котором возникла ошибка.",
    description: "Контур документооборота и ЭДО.",
  },
  subscription_change: {
    subject: "Изменение тарифа или подписки",
    message: "Опишите, какой тариф или модуль нужно подключить либо изменить.",
    description: "Контур подписки и коммерческих условий.",
  },
};

export function SupportTicketNewPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [priority, setPriority] = useState<SupportTicketPriority>("NORMAL");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const topic = searchParams.get("topic") ?? "";
  const topicPreset = useMemo(() => TOPIC_PRESETS[topic] ?? null, [topic]);

  useEffect(() => {
    if (!topicPreset) return;
    setSubject((current) => (current.trim().length ? current : topicPreset.subject));
    setMessage((current) => (current.trim().length ? current : topicPreset.message));
  }, [topicPreset]);

  if (!user) {
    return <AppErrorState message="Требуется авторизация." />;
  }

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!subject.trim() || !message.trim()) {
      setError("Опишите тему обращения и саму проблему, чтобы мы могли начать разбор.");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      const ticket = await createSupportTicket({ subject: subject.trim(), message: message.trim(), priority }, user);
      navigate(`/client/support/${ticket.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось создать обращение");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="stack">
      <section className="card stack">
        <div>
          <h2>Создать обращение</h2>
          <p className="muted">Опишите проблему и следующий нужный шаг. Мы направим запрос в правильный контур поддержки.</p>
        </div>
        {topicPreset ? (
          <AppEmptyState
            title="Контур обращения уже выбран"
            description={topicPreset.description}
            action={<Link className="ghost" to="/client/support">Вернуться к списку обращений</Link>}
          />
        ) : null}
        {error ? <AppErrorState message={error} variant="compact" /> : null}
        <form className="stack" onSubmit={handleSubmit}>
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
          <div className="actions">
            <button className="primary" type="submit" disabled={!subject.trim() || !message.trim() || isSubmitting}>
              {isSubmitting ? "Создаём..." : "Создать обращение"}
            </button>
            <button className="ghost" type="button" onClick={() => navigate("/client/support")}>
              Отмена
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
