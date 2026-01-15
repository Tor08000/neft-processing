import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import {
  blockCard,
  fetchCard,
  fetchCardAccess,
  fetchCardTransactions,
  grantCardAccess,
  revokeCardAccess,
  unblockCard,
  updateCardLimit,
} from "../api/cards";
import { ApiError } from "../api/http";
import { AppErrorState, AppForbiddenState, AppLoadingState } from "../components/states";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";
import { MoneyValue } from "../components/common/MoneyValue";
import type { CardLimit, ClientCard } from "../types/cards";
import { formatDateTime } from "../utils/format";
import { hasAnyRole } from "../utils/roles";

const DEFAULT_LIMITS: CardLimit[] = [
  { type: "DAILY_AMOUNT", value: 0, window: "DAY" },
  { type: "MONTHLY_AMOUNT", value: 0, window: "MONTH" },
];

type AccessEntry = {
  user_id: string;
  scope: string;
  effective_from?: string | null;
};

type CardTransaction = {
  id: string;
  operation_type: string;
  status: string;
  amount: number;
  currency: string;
  performed_at: string;
};

export function ClientCardDetailsPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { toast, showToast } = useToast();

  const [card, setCard] = useState<ClientCard | null>(null);
  const [limitDraft, setLimitDraft] = useState<Record<string, number>>({});
  const [error, setError] = useState<{ message: string; status?: number } | null>(null);
  const [loading, setLoading] = useState(true);

  const [accessItems, setAccessItems] = useState<AccessEntry[]>([]);
  const [accessDraft, setAccessDraft] = useState({ userId: "", scope: "VIEW" });
  const [accessError, setAccessError] = useState<string | null>(null);

  const [transactions, setTransactions] = useState<CardTransaction[]>([]);
  const [transactionsError, setTransactionsError] = useState<string | null>(null);

  const canManage = hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_FLEET_MANAGER"]);

  const loadCard = async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchCard(id, user);
      setCard(data);
      const initial: Record<string, number> = {};
      data.limits.forEach((limit) => {
        initial[limit.type] = limit.value;
      });
      setLimitDraft(initial);
    } catch (err) {
      if (err instanceof ApiError) {
        setError({ message: err.message, status: err.status });
      } else {
        setError({ message: err instanceof Error ? err.message : "Ошибка загрузки карты" });
      }
    } finally {
      setLoading(false);
    }
  };

  const loadAccess = async () => {
    if (!id || !canManage) return;
    setAccessError(null);
    try {
      const response = await fetchCardAccess(id, user);
      setAccessItems(response.items ?? []);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setAccessError("Недостаточно прав для управления доступами.");
        return;
      }
      setAccessError(err instanceof Error ? err.message : "Не удалось загрузить доступы.");
    }
  };

  const loadTransactions = async () => {
    if (!id) return;
    setTransactionsError(null);
    try {
      const response = await fetchCardTransactions(id, user);
      setTransactions(response);
    } catch (err) {
      setTransactionsError(err instanceof Error ? err.message : "Не удалось загрузить операции.");
    }
  };

  useEffect(() => {
    void loadCard();
  }, [id, user]);

  useEffect(() => {
    void loadAccess();
  }, [id, user, canManage]);

  useEffect(() => {
    void loadTransactions();
  }, [id, user]);

  const limitList = useMemo(() => {
    if (!card) return DEFAULT_LIMITS;
    const known = new Map(card.limits.map((l) => [l.type, l] as const));
    return DEFAULT_LIMITS.map((preset) => known.get(preset.type) ?? preset);
  }, [card]);

  const toggleStatus = async () => {
    if (!card) return;
    const confirmed =
      typeof window === "undefined"
        ? true
        : window.confirm(card.status === "ACTIVE" ? "Заблокировать карту?" : "Разблокировать карту?");
    if (!confirmed) return;
    const fn = card.status === "ACTIVE" ? blockCard : unblockCard;
    try {
      const response = await fn(card.id, user);
      setCard({ ...card, status: response.status });
      showToast({
        kind: "success",
        text: card.status === "ACTIVE" ? "Карта заблокирована" : "Карта разблокирована",
      });
    } catch (err) {
      setError({ message: err instanceof Error ? err.message : "Ошибка обновления статуса" });
    }
  };

  const submitLimits = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!card) return;
    try {
      const updates: CardLimit[] = limitList.map((limit) => ({
        ...limit,
        value: Number(limitDraft[limit.type] ?? limit.value),
      }));
      let latest: ClientCard = card;
      for (const update of updates) {
        latest = await updateCardLimit(card.id, update, user);
      }
      setCard(latest);
      showToast({ kind: "success", text: "Лимиты обновлены" });
    } catch (err) {
      setError({ message: err instanceof Error ? err.message : "Не удалось обновить лимиты" });
    }
  };

  const handleGrantAccess = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!id || !accessDraft.userId.trim()) return;
    setAccessError(null);
    try {
      await grantCardAccess(id, { user_id: accessDraft.userId.trim(), scope: accessDraft.scope }, user);
      setAccessDraft({ userId: "", scope: accessDraft.scope });
      showToast({ kind: "success", text: "Доступ выдан" });
      await loadAccess();
    } catch (err) {
      setAccessError(err instanceof Error ? err.message : "Не удалось выдать доступ.");
    }
  };

  const handleRevoke = async (userId: string) => {
    if (!id) return;
    const confirmed =
      typeof window === "undefined" ? true : window.confirm("Отозвать доступ пользователя?");
    if (!confirmed) return;
    setAccessError(null);
    try {
      await revokeCardAccess(id, userId, user);
      showToast({ kind: "success", text: "Доступ отозван" });
      await loadAccess();
    } catch (err) {
      setAccessError(err instanceof Error ? err.message : "Не удалось отозвать доступ.");
    }
  };

  if (loading) {
    return <AppLoadingState label="Загрузка данных карты..." />;
  }

  if (error) {
    if (error.status === 403) {
      return <AppForbiddenState message="Недостаточно прав для доступа к карте." />;
    }
    return <AppErrorState message={error.message} status={error.status} />;
  }

  if (!card) {
    return (
      <div className="card error" role="alert">
        Карта не найдена
        <button className="ghost" onClick={() => navigate(-1)} type="button">
          Назад
        </button>
      </div>
    );
  }

  return (
    <div className="stack">
      <div className="card">
        <div className="card__header">
          <div>
            <h2>Карта {card.pan_masked ?? card.id}</h2>
            <p className="muted">Статус и базовая информация</p>
          </div>
          {canManage ? (
            <button className="secondary" type="button" onClick={() => void toggleStatus()}>
              {card.status === "ACTIVE" ? "Заблокировать" : "Разблокировать"}
            </button>
          ) : null}
        </div>

        <dl className="meta-grid">
          <div>
            <dt className="label">ID карты</dt>
            <dd>{card.id}</dd>
          </div>
          <div>
            <dt className="label">Статус</dt>
            <dd>
              <span className={`pill pill--${card.status === "ACTIVE" ? "success" : "warning"}`}>{card.status}</span>
            </dd>
          </div>
        </dl>
      </div>

      <div className="card">
        <div className="card__header">
          <div>
            <h3>Лимиты</h3>
            <p className="muted">Обновите дневные и месячные лимиты по карте.</p>
          </div>
        </div>
        {canManage ? (
          <form className="form-grid" onSubmit={submitLimits}>
            {limitList.map((limit) => (
              <label key={limit.type} className="form-field">
                <span className="label">
                  {limit.type} ({limit.window})
                </span>
                <input
                  type="number"
                  min={0}
                  value={limitDraft[limit.type] ?? limit.value}
                  onChange={(e) =>
                    setLimitDraft((prev) => ({
                      ...prev,
                      [limit.type]: Number(e.target.value),
                    }))
                  }
                />
              </label>
            ))}
            <div className="form-actions">
              <button type="submit">Сохранить</button>
            </div>
          </form>
        ) : (
          <div className="muted">Просмотр доступен только администраторам.</div>
        )}
      </div>

      <div className="card">
        <div className="card__header">
          <div>
            <h3>Доступы</h3>
            <p className="muted">Выдайте или отзовите доступ сотрудников к карте.</p>
          </div>
        </div>
        {canManage ? (
          <>
            <form className="form-grid" onSubmit={handleGrantAccess}>
              <label className="form-field">
                <span className="label">User ID</span>
                <input
                  value={accessDraft.userId}
                  onChange={(event) => setAccessDraft((prev) => ({ ...prev, userId: event.target.value }))}
                  placeholder="user-id"
                />
              </label>
              <label className="form-field">
                <span className="label">Роль доступа</span>
                <select
                  value={accessDraft.scope}
                  onChange={(event) => setAccessDraft((prev) => ({ ...prev, scope: event.target.value }))}
                >
                  <option value="VIEW">VIEW</option>
                  <option value="USE">USE</option>
                  <option value="MANAGE">MANAGE</option>
                </select>
              </label>
              <div className="form-actions">
                <button type="submit" disabled={!accessDraft.userId.trim()}>
                  Выдать доступ
                </button>
              </div>
            </form>
            {accessError ? <div className="notice error">{accessError}</div> : null}
            {accessItems.length ? (
              <table className="table">
                <thead>
                  <tr>
                    <th>User ID</th>
                    <th>Scope</th>
                    <th>Дата</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {accessItems.map((item) => (
                    <tr key={`${item.user_id}-${item.scope}`}>
                      <td>{item.user_id}</td>
                      <td>{item.scope}</td>
                      <td>{item.effective_from ? formatDateTime(item.effective_from) : "—"}</td>
                      <td>
                        <button type="button" className="ghost" onClick={() => void handleRevoke(item.user_id)}>
                          Отозвать
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="muted">Доступов пока нет.</div>
            )}
          </>
        ) : (
          <div className="muted">Управление доступами доступно только администраторам.</div>
        )}
      </div>

      <div className="card">
        <div className="card__header">
          <div>
            <h3>Операции</h3>
            <p className="muted">Последние операции по карте.</p>
          </div>
        </div>
        {transactionsError ? <div className="notice error">{transactionsError}</div> : null}
        {transactions.length ? (
          <table className="table">
            <thead>
              <tr>
                <th>Дата</th>
                <th>Тип</th>
                <th>Статус</th>
                <th>Сумма</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((item) => (
                <tr key={item.id}>
                  <td>{formatDateTime(item.performed_at)}</td>
                  <td>{item.operation_type}</td>
                  <td>{item.status}</td>
                  <td>
                    <MoneyValue amount={item.amount} currency={item.currency} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="muted">Операций пока нет.</div>
        )}
      </div>
      {toast ? <Toast toast={toast} onClose={() => showToast(null)} /> : null}
    </div>
  );
}
