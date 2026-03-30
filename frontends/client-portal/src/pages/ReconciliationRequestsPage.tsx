import { useEffect, useMemo, useState } from "react";
import { createReconciliationRequest, downloadReconciliationResult, fetchReconciliationRequests } from "../api/reconciliation";
import { useAuth } from "../auth/AuthContext";
import type { ReconciliationRequest } from "../types/reconciliation";
import { CopyButton } from "../components/CopyButton";
import { formatDate } from "../utils/format";
import { getReconciliationStatusLabel, getReconciliationStatusTone } from "../utils/reconciliation";

const ACTION_ROLES = ["CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_ACCOUNTANT"];

export function ReconciliationRequestsPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<ReconciliationRequest[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ date_from: "", date_to: "", note: "" });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const canAct = useMemo(() => {
    const roles = user?.roles ?? [];
    return roles.some((role) => ACTION_ROLES.includes(role));
  }, [user?.roles]);

  const loadRequests = () => {
    setIsLoading(true);
    setError(null);
    fetchReconciliationRequests(user)
      .then((data) => setItems(data.items ?? []))
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    loadRequests();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  const existingForPeriod = useMemo(() => {
    if (!form.date_from || !form.date_to) return null;
    return items.find(
      (item) =>
        item.date_from === form.date_from &&
        item.date_to === form.date_to &&
        ["REQUESTED", "IN_PROGRESS", "GENERATED", "SENT"].includes(item.status),
    );
  }, [form.date_from, form.date_to, items]);

  const handleSubmit = async (evt: React.FormEvent<HTMLFormElement>) => {
    evt.preventDefault();
    if (!form.date_from || !form.date_to) {
      setError("Укажите период");
      return;
    }
    if (existingForPeriod) {
      setNotice(`Запрос уже создан. Статус: ${getReconciliationStatusLabel(existingForPeriod.status)}`);
      return;
    }
    setIsSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const created = await createReconciliationRequest(user, {
        date_from: form.date_from,
        date_to: form.date_to,
        note: form.note || undefined,
      });
      setItems((prev) => {
        if (prev.some((item) => item.id === created.id)) {
          return prev;
        }
        return [created, ...prev];
      });
      setForm({ date_from: "", date_to: "", note: "" });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDownload = async (item: ReconciliationRequest) => {
    try {
      await downloadReconciliationResult(item.id, user);
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <div className="card">
      <div className="card__header">
        <div>
          <h2>Акты сверки</h2>
          <p className="muted">Создайте запрос на акт сверки и отслеживайте статус.</p>
        </div>
      </div>

      {error ? (
        <div className="card error" role="alert">
          {error}
        </div>
      ) : null}
      {notice ? (
        <div className="card" role="status">
          {notice}
        </div>
      ) : null}

      <div className="card__section">
        <h3>Новый запрос</h3>
        <form className="form-grid" onSubmit={handleSubmit}>
          <label>
            Период с
            <input
              type="date"
              value={form.date_from}
              onChange={(evt) => setForm((prev) => ({ ...prev, date_from: evt.target.value }))}
              disabled={!canAct || isSubmitting}
            />
          </label>
          <label>
            Период по
            <input
              type="date"
              value={form.date_to}
              onChange={(evt) => setForm((prev) => ({ ...prev, date_to: evt.target.value }))}
              disabled={!canAct || isSubmitting}
            />
          </label>
          <label className="form-grid__full">
            Комментарий
            <textarea
              value={form.note}
              onChange={(evt) => setForm((prev) => ({ ...prev, note: evt.target.value }))}
              placeholder="Например: по всем операциям за месяц"
              rows={3}
              disabled={!canAct || isSubmitting}
            />
          </label>
          <div className="form-grid__actions">
            <button type="submit" disabled={!canAct || isSubmitting}>
              {existingForPeriod
                ? `Запрос уже создан (${getReconciliationStatusLabel(existingForPeriod.status)})`
                : isSubmitting
                  ? "Отправляем..."
                  : "Отправить запрос"}
            </button>
            {!canAct ? <span className="muted small">Доступно только администраторам клиента.</span> : null}
          </div>
        </form>
      </div>

      <div className="card__section">
        <h3>История запросов</h3>
        {isLoading ? (
          <div className="skeleton-stack">
            <div className="skeleton-line" />
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        ) : items.length === 0 ? (
          <div className="empty-state">
            <p className="muted">Запросов пока нет.</p>
            <p className="muted small">Запросите акт сверки, чтобы получить официальный документ.</p>
            <button type="button" className="ghost" onClick={loadRequests}>
              Обновить
            </button>
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Период</th>
                <th>Статус</th>
                <th>Комментарий</th>
                <th>SHA256</th>
                <th>Создан</th>
                <th>Файл</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const hasResult = Boolean(item.result_object_key);
                const canDownload = hasResult && ["GENERATED", "SENT", "ACKNOWLEDGED"].includes(item.status);
                return (
                  <tr key={item.id}>
                    <td>
                      <div className="stack-inline">
                        <span className="muted small">{item.id.slice(0, 8)}</span>
                        <CopyButton value={item.id} />
                      </div>
                    </td>
                    <td>
                      {formatDate(item.date_from)} — {formatDate(item.date_to)}
                    </td>
                    <td>
                      <span className={`pill ${getReconciliationStatusTone(item.status)}`}>
                        {getReconciliationStatusLabel(item.status)}
                      </span>
                    </td>
                    <td>{item.note_client || "—"}</td>
                    <td>
                      {item.result_hash_sha256 ? (
                        <div className="stack-inline">
                          <span className="muted small">{item.result_hash_sha256.slice(0, 10)}…</span>
                          <CopyButton value={item.result_hash_sha256} />
                        </div>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td>{item.requested_at ? formatDate(item.requested_at) : "—"}</td>
                    <td>
                      {canDownload ? (
                        <button type="button" className="link-button" onClick={() => handleDownload(item)}>
                          Скачать
                        </button>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
