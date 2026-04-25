import { useCallback, useEffect, useMemo, useState } from "react";
import { createReconciliationRequest, downloadReconciliationResult, fetchReconciliationRequests } from "../api/reconciliation";
import { useAuth } from "../auth/AuthContext";
import { Table, type Column } from "../components/common/Table";
import { AppEmptyState, AppErrorState } from "../components/states";
import type { ReconciliationRequest } from "../types/reconciliation";
import { CopyButton } from "../components/CopyButton";
import { formatDate } from "../utils/format";
import { getReconciliationStatusLabel, getReconciliationStatusTone } from "../utils/reconciliation";

const ACTION_ROLES = ["CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_ACCOUNTANT"];

export function ReconciliationRequestsPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<ReconciliationRequest[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [form, setForm] = useState({ date_from: "", date_to: "", note: "" });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const canAct = useMemo(() => {
    const roles = user?.roles ?? [];
    return roles.some((role) => ACTION_ROLES.includes(role));
  }, [user?.roles]);

  const loadRequests = useCallback(() => {
    setIsLoading(true);
    setLoadError(null);
    fetchReconciliationRequests(user)
      .then((data) => setItems(data.items ?? []))
      .catch((err: Error) => setLoadError(err.message))
      .finally(() => setIsLoading(false));
  }, [user]);

  useEffect(() => {
    loadRequests();
  }, [loadRequests]);

  const existingForPeriod = useMemo(() => {
    if (!form.date_from || !form.date_to) return null;
    return items.find(
      (item) =>
        item.date_from === form.date_from &&
        item.date_to === form.date_to &&
      ["REQUESTED", "IN_PROGRESS", "GENERATED", "SENT"].includes(item.status),
    );
  }, [form.date_from, form.date_to, items]);
  const invalidPeriod = useMemo(
    () => Boolean(form.date_from && form.date_to && form.date_from > form.date_to),
    [form.date_from, form.date_to],
  );

  const handleSubmit = async (evt: React.FormEvent<HTMLFormElement>) => {
    evt.preventDefault();
    setActionError(null);
    setNotice(null);
    if (!form.date_from || !form.date_to) {
      setActionError("Укажите период");
      return;
    }
    if (invalidPeriod) {
      setActionError("Дата окончания должна быть не раньше даты начала.");
      return;
    }
    if (existingForPeriod) {
      setNotice(`Запрос уже создан. Статус: ${getReconciliationStatusLabel(existingForPeriod.status)}`);
      return;
    }
    setIsSubmitting(true);
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
      setNotice("Запрос создан. Следите за статусом в истории ниже.");
    } catch (err) {
      setActionError((err as Error).message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDownload = async (item: ReconciliationRequest) => {
    try {
      await downloadReconciliationResult(item.id, user);
      setActionError(null);
    } catch (err) {
      setActionError((err as Error).message);
    }
  };

  const columns: Column<ReconciliationRequest>[] = [
    {
      key: "id",
      title: "ID",
      render: (item) => (
        <div className="stack-inline">
          <span className="muted small">{item.id.slice(0, 8)}</span>
          <CopyButton value={item.id} />
        </div>
      ),
    },
    {
      key: "period",
      title: "Период",
      render: (item) => (
        <>
          {formatDate(item.date_from)} — {formatDate(item.date_to)}
        </>
      ),
    },
    {
      key: "status",
      title: "Статус",
      render: (item) => (
        <span className={`pill ${getReconciliationStatusTone(item.status)}`}>
          {getReconciliationStatusLabel(item.status)}
        </span>
      ),
    },
    {
      key: "note",
      title: "Комментарий",
      render: (item) => item.note_client || "—",
    },
    {
      key: "hash",
      title: "SHA256",
      render: (item) =>
        item.result_hash_sha256 ? (
          <div className="stack-inline">
            <span className="muted small">{item.result_hash_sha256.slice(0, 10)}…</span>
            <CopyButton value={item.result_hash_sha256} />
          </div>
        ) : (
          <span className="muted">—</span>
        ),
    },
    {
      key: "created",
      title: "Создан",
      render: (item) => (item.requested_at ? formatDate(item.requested_at) : "—"),
    },
    {
      key: "file",
      title: "Файл",
      render: (item) => {
        const hasResult = Boolean(item.result_object_key);
        const canDownload = hasResult && ["GENERATED", "SENT", "ACKNOWLEDGED"].includes(item.status);
        return canDownload ? (
          <button type="button" className="link-button" onClick={() => void handleDownload(item)}>
            Скачать
          </button>
        ) : (
          <span className="muted">—</span>
        );
      },
    },
  ];

  return (
    <div className="card">
      <div className="card__header">
        <div>
          <h2>Акты сверки</h2>
          <p className="muted">Создайте запрос на акт сверки и отслеживайте статус.</p>
        </div>
      </div>

      {actionError ? (
        <div className="card error" role="alert">
          {actionError}
        </div>
      ) : null}
      {notice ? (
        <div className="card" role="status">
          {notice}
        </div>
      ) : null}

      <div className="card__section">
        <h3>Новый запрос</h3>
        {!canAct ? (
          <AppEmptyState
            title="Создание запроса недоступно"
            description="Новый акт сверки может запросить владелец, администратор или бухгалтер клиента."
          />
        ) : (
          <>
            {actionError ? <AppErrorState message={actionError} variant="compact" /> : null}
            {notice ? (
              <div className="card" role="status">
                {notice}
              </div>
            ) : null}
            <form className="form-grid" onSubmit={handleSubmit}>
              <label>
                Период с
                <input
                  type="date"
                  value={form.date_from}
                  onChange={(evt) => setForm((prev) => ({ ...prev, date_from: evt.target.value }))}
                  disabled={isSubmitting}
                />
              </label>
              <label>
                Период по
                <input
                  type="date"
                  value={form.date_to}
                  onChange={(evt) => setForm((prev) => ({ ...prev, date_to: evt.target.value }))}
                  disabled={isSubmitting}
                />
              </label>
              <label className="form-grid__full">
                Комментарий
                <textarea
                  value={form.note}
                  onChange={(evt) => setForm((prev) => ({ ...prev, note: evt.target.value }))}
                  placeholder="Например: по всем операциям за месяц"
                  rows={3}
                  disabled={isSubmitting}
                />
              </label>
              <div className="form-grid__actions">
                <button type="submit" disabled={isSubmitting || invalidPeriod || Boolean(existingForPeriod)}>
                  {existingForPeriod
                    ? `Запрос уже создан (${getReconciliationStatusLabel(existingForPeriod.status)})`
                    : isSubmitting
                      ? "Отправляем..."
                      : "Отправить запрос"}
                </button>
                {invalidPeriod ? (
                  <span className="muted small">Проверьте период: дата окончания не должна быть раньше даты начала.</span>
                ) : existingForPeriod ? (
                  <span className="muted small">
                    За этот период уже есть активный запрос: {getReconciliationStatusLabel(existingForPeriod.status)}.
                  </span>
                ) : (
                  <span className="muted small">История ниже покажет статус и готовый файл для скачивания.</span>
                )}
              </div>
            </form>
          </>
        )}
      </div>

      <div className="card__section">
        <h3>История запросов</h3>
        <Table
          columns={columns}
          data={items}
          loading={isLoading}
          rowKey={(item) => item.id}
          toolbar={
            <div className="table-toolbar">
              <div className="toolbar-actions">
                <button type="button" className="button secondary" onClick={loadRequests} disabled={isLoading}>
                  Обновить
                </button>
              </div>
            </div>
          }
          errorState={
            loadError
              ? {
                  title: "Не удалось загрузить историю сверки",
                  description: loadError,
                  actionLabel: "Повторить",
                  actionOnClick: loadRequests,
                }
              : undefined
          }
          emptyState={{
            title: "Запросов пока нет",
            description: "Запросите акт сверки, чтобы получить официальный документ.",
            actionLabel: "Обновить",
            actionOnClick: loadRequests,
          }}
          footer={loadError ? null : <div className="table-footer__content muted">Запросов: {items.length}</div>}
        />
      </div>
    </div>
  );
}
