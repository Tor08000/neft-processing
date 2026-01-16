import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { createExportJob } from "../api/exports";
import { ApiError, ValidationError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { AppForbiddenState } from "../components/states";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";
import { hasAnyRole } from "../utils/roles";

const MAX_EXPORT_ROWS = 5000;

const resolveErrorMessage = (error: unknown): string => {
  if (error instanceof ValidationError) {
    return "Укажите обязательные фильтры";
  }
  if (error instanceof ApiError) {
    if (error.status === 413) {
      return "Слишком большой объём данных";
    }
    if (error.status === 403) {
      return "Доступ запрещён";
    }
    return error.message || "Ошибка выгрузки";
  }
  if (error instanceof Error) {
    return error.message || "Ошибка выгрузки";
  }
  return "Ошибка выгрузки";
};

const splitValues = (value: string): string[] =>
  value
    .split(/[\s,]+/)
    .map((item) => item.trim())
    .filter(Boolean);

export function ReportsPage() {
  const { user } = useAuth();
  const { toast, showToast } = useToast();
  const [showExportHint, setShowExportHint] = useState(false);
  const [cardsFilters, setCardsFilters] = useState({ status: "", driverId: "", from: "", to: "" });
  const [usersFilters, setUsersFilters] = useState({ role: "", status: "", from: "", to: "" });
  const [transactionsFilters, setTransactionsFilters] = useState({
    cards: "",
    status: "",
    from: "",
    to: "",
    minAmount: "",
    maxAmount: "",
  });
  const [documentsFilters, setDocumentsFilters] = useState({ type: "", status: "", from: "", to: "" });

  const [cardsState, setCardsState] = useState({ loading: false, error: "" });
  const [usersState, setUsersState] = useState({ loading: false, error: "" });
  const [transactionsState, setTransactionsState] = useState({ loading: false, error: "" });
  const [documentsState, setDocumentsState] = useState({ loading: false, error: "" });

  const canAccessCards = useMemo(
    () => hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_FLEET_MANAGER"]),
    [user],
  );
  const canAccessUsers = useMemo(
    () => hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_ACCOUNTANT"]),
    [user],
  );
  const canAccessTransactions = useMemo(
    () => hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_ACCOUNTANT", "CLIENT_FLEET_MANAGER"]),
    [user],
  );
  const canAccessDocuments = useMemo(
    () => hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_ACCOUNTANT"]),
    [user],
  );

  const hasAnyAccess = canAccessCards || canAccessUsers || canAccessTransactions || canAccessDocuments;

  if (!user) {
    return <AppForbiddenState message="Требуется авторизация" />;
  }

  if (!hasAnyAccess) {
    return <AppForbiddenState message="Недостаточно прав для доступа к выгрузкам" />;
  }

  return (
    <div className="stack">
      <div className="card">
        <div className="card__header">
          <div>
            <h2>Reports / Exports</h2>
            <p className="muted">Выгружайте CSV с учётом фильтров. Максимум {MAX_EXPORT_ROWS} строк.</p>
            {showExportHint ? (
              <p className="muted">
                Отчёт поставлен в очередь. <Link to="/client/exports">Перейти в Экспорты</Link>
              </p>
            ) : null}
          </div>
        </div>
      </div>

      {canAccessCards ? (
        <section className="card">
          <div className="card__header">
            <div>
              <h3>Cards</h3>
              <p className="muted">Карты с состоянием, назначением и лимитами.</p>
            </div>
            <button
              type="button"
              className="neft-btn neft-btn-primary"
              disabled={cardsState.loading}
              title="Экспортирует список карт текущей организации"
              onClick={async () => {
                setCardsState({ loading: true, error: "" });
                try {
                  await createExportJob(
                    "cards",
                    {
                      status: cardsFilters.status,
                      driver_id: cardsFilters.driverId,
                      from: cardsFilters.from,
                      to: cardsFilters.to,
                    },
                    user,
                  );
                  showToast({ kind: "success", text: "Отчёт поставлен в очередь" });
                  setShowExportHint(true);
                } catch (error) {
                  setCardsState({ loading: false, error: resolveErrorMessage(error) });
                  return;
                }
                setCardsState({ loading: false, error: "" });
              }}
            >
              {cardsState.loading ? "Ставим в очередь…" : "Сформировать отчёт"}
            </button>
          </div>
          <div className="filters">
            <div className="filter">
              <label htmlFor="cards-status">Статус</label>
              <select
                id="cards-status"
                value={cardsFilters.status}
                onChange={(event) => setCardsFilters((prev) => ({ ...prev, status: event.target.value }))}
              >
                <option value="">Все</option>
                <option value="ACTIVE">Активные</option>
                <option value="BLOCKED">Заблокированные</option>
              </select>
            </div>
            <div className="filter">
              <label htmlFor="cards-driver">Driver ID</label>
              <input
                id="cards-driver"
                type="text"
                value={cardsFilters.driverId}
                onChange={(event) => setCardsFilters((prev) => ({ ...prev, driverId: event.target.value }))}
                placeholder="driver-uuid"
              />
            </div>
            <div className="filter">
              <label htmlFor="cards-from">Создано с</label>
              <input
                id="cards-from"
                type="date"
                value={cardsFilters.from}
                onChange={(event) => setCardsFilters((prev) => ({ ...prev, from: event.target.value }))}
              />
            </div>
            <div className="filter">
              <label htmlFor="cards-to">Создано по</label>
              <input
                id="cards-to"
                type="date"
                value={cardsFilters.to}
                onChange={(event) => setCardsFilters((prev) => ({ ...prev, to: event.target.value }))}
              />
            </div>
          </div>
          {cardsState.error ? <div className="muted">{cardsState.error}</div> : null}
        </section>
      ) : null}

      {canAccessUsers ? (
        <section className="card">
          <div className="card__header">
            <div>
              <h3>Users</h3>
              <p className="muted">Пользователи организации с ролями и статусами.</p>
            </div>
            <button
              type="button"
              className="neft-btn neft-btn-primary"
              disabled={usersState.loading}
              title="Экспортирует пользователей текущей организации"
              onClick={async () => {
                setUsersState({ loading: true, error: "" });
                try {
                  await createExportJob(
                    "users",
                    {
                      role: usersFilters.role,
                      status: usersFilters.status,
                      from: usersFilters.from,
                      to: usersFilters.to,
                    },
                    user,
                  );
                  showToast({ kind: "success", text: "Отчёт поставлен в очередь" });
                  setShowExportHint(true);
                } catch (error) {
                  setUsersState({ loading: false, error: resolveErrorMessage(error) });
                  return;
                }
                setUsersState({ loading: false, error: "" });
              }}
            >
              {usersState.loading ? "Ставим в очередь…" : "Сформировать отчёт"}
            </button>
          </div>
          <div className="filters">
            <div className="filter">
              <label htmlFor="users-role">Роль</label>
              <select
                id="users-role"
                value={usersFilters.role}
                onChange={(event) => setUsersFilters((prev) => ({ ...prev, role: event.target.value }))}
              >
                <option value="">Все</option>
                <option value="CLIENT_OWNER">OWNER</option>
                <option value="CLIENT_ADMIN">ADMIN</option>
                <option value="CLIENT_ACCOUNTANT">ACCOUNTANT</option>
                <option value="CLIENT_FLEET_MANAGER">FLEET_MANAGER</option>
                <option value="CLIENT_USER">USER</option>
              </select>
            </div>
            <div className="filter">
              <label htmlFor="users-status">Статус</label>
              <select
                id="users-status"
                value={usersFilters.status}
                onChange={(event) => setUsersFilters((prev) => ({ ...prev, status: event.target.value }))}
              >
                <option value="">Все</option>
                <option value="ACTIVE">Активные</option>
                <option value="INVITED">Приглашённые</option>
                <option value="DISABLED">Отключённые</option>
              </select>
            </div>
            <div className="filter">
              <label htmlFor="users-from">Создано с</label>
              <input
                id="users-from"
                type="date"
                value={usersFilters.from}
                onChange={(event) => setUsersFilters((prev) => ({ ...prev, from: event.target.value }))}
              />
            </div>
            <div className="filter">
              <label htmlFor="users-to">Создано по</label>
              <input
                id="users-to"
                type="date"
                value={usersFilters.to}
                onChange={(event) => setUsersFilters((prev) => ({ ...prev, to: event.target.value }))}
              />
            </div>
          </div>
          {usersState.error ? <div className="muted">{usersState.error}</div> : null}
        </section>
      ) : null}

      {canAccessTransactions ? (
        <section className="card">
          <div className="card__header">
            <div>
              <h3>Transactions</h3>
              <p className="muted">Операции с картами, датой, суммой и статусом. Диапазон дат обязателен.</p>
            </div>
            <button
              type="button"
              className="neft-btn neft-btn-primary"
              disabled={transactionsState.loading || !transactionsFilters.from || !transactionsFilters.to}
              title="Экспортирует операции по выбранным фильтрам"
              onClick={async () => {
                setTransactionsState({ loading: true, error: "" });
                try {
                  await createExportJob(
                    "transactions",
                    {
                      card_ids: splitValues(transactionsFilters.cards),
                      status: transactionsFilters.status,
                      from: transactionsFilters.from,
                      to: transactionsFilters.to,
                      min_amount: transactionsFilters.minAmount,
                      max_amount: transactionsFilters.maxAmount,
                    },
                    user,
                  );
                  showToast({ kind: "success", text: "Отчёт поставлен в очередь" });
                  setShowExportHint(true);
                } catch (error) {
                  setTransactionsState({ loading: false, error: resolveErrorMessage(error) });
                  return;
                }
                setTransactionsState({ loading: false, error: "" });
              }}
            >
              {transactionsState.loading ? "Ставим в очередь…" : "Сформировать отчёт"}
            </button>
          </div>
          <div className="filters">
            <div className="filter">
              <label htmlFor="tx-cards">Card IDs</label>
              <input
                id="tx-cards"
                type="text"
                value={transactionsFilters.cards}
                onChange={(event) => setTransactionsFilters((prev) => ({ ...prev, cards: event.target.value }))}
                placeholder="card-1, card-2"
              />
            </div>
            <div className="filter">
              <label htmlFor="tx-status">Статус</label>
              <select
                id="tx-status"
                value={transactionsFilters.status}
                onChange={(event) => setTransactionsFilters((prev) => ({ ...prev, status: event.target.value }))}
              >
                <option value="">Все</option>
                <option value="AUTHORIZED">Авторизована</option>
                <option value="COMPLETED">Завершена</option>
                <option value="DECLINED">Отклонена</option>
                <option value="CANCELLED">Отменена</option>
              </select>
            </div>
            <div className="filter">
              <label htmlFor="tx-from">Дата с</label>
              <input
                id="tx-from"
                type="date"
                value={transactionsFilters.from}
                onChange={(event) => setTransactionsFilters((prev) => ({ ...prev, from: event.target.value }))}
              />
            </div>
            <div className="filter">
              <label htmlFor="tx-to">Дата по</label>
              <input
                id="tx-to"
                type="date"
                value={transactionsFilters.to}
                onChange={(event) => setTransactionsFilters((prev) => ({ ...prev, to: event.target.value }))}
              />
            </div>
            <div className="filter">
              <label htmlFor="tx-min">Сумма от</label>
              <input
                id="tx-min"
                type="number"
                value={transactionsFilters.minAmount}
                onChange={(event) => setTransactionsFilters((prev) => ({ ...prev, minAmount: event.target.value }))}
              />
            </div>
            <div className="filter">
              <label htmlFor="tx-max">Сумма до</label>
              <input
                id="tx-max"
                type="number"
                value={transactionsFilters.maxAmount}
                onChange={(event) => setTransactionsFilters((prev) => ({ ...prev, maxAmount: event.target.value }))}
              />
            </div>
          </div>
          {transactionsState.error ? <div className="muted">{transactionsState.error}</div> : null}
        </section>
      ) : null}

      {canAccessDocuments ? (
        <section className="card">
          <div className="card__header">
            <div>
              <h3>Documents</h3>
              <p className="muted">Метаданные документов без вложений.</p>
            </div>
            <button
              type="button"
              className="neft-btn neft-btn-primary"
              disabled={documentsState.loading}
              title="Экспортирует метаданные документов"
              onClick={async () => {
                setDocumentsState({ loading: true, error: "" });
                try {
                  await createExportJob(
                    "documents",
                    {
                      type: documentsFilters.type,
                      status: documentsFilters.status,
                      from: documentsFilters.from,
                      to: documentsFilters.to,
                    },
                    user,
                  );
                  showToast({ kind: "success", text: "Отчёт поставлен в очередь" });
                  setShowExportHint(true);
                } catch (error) {
                  setDocumentsState({ loading: false, error: resolveErrorMessage(error) });
                  return;
                }
                setDocumentsState({ loading: false, error: "" });
              }}
            >
              {documentsState.loading ? "Ставим в очередь…" : "Сформировать отчёт"}
            </button>
          </div>
          <div className="filters">
            <div className="filter">
              <label htmlFor="docs-type">Тип</label>
              <select
                id="docs-type"
                value={documentsFilters.type}
                onChange={(event) => setDocumentsFilters((prev) => ({ ...prev, type: event.target.value }))}
              >
                <option value="">Все</option>
                <option value="INVOICE">Invoice</option>
                <option value="ACT">Act</option>
                <option value="CONTRACT">Contract</option>
              </select>
            </div>
            <div className="filter">
              <label htmlFor="docs-status">Статус</label>
              <select
                id="docs-status"
                value={documentsFilters.status}
                onChange={(event) => setDocumentsFilters((prev) => ({ ...prev, status: event.target.value }))}
              >
                <option value="">Все</option>
                <option value="DRAFT">Draft</option>
                <option value="ISSUED">Issued</option>
                <option value="ACKNOWLEDGED">Acknowledged</option>
                <option value="FINALIZED">Finalized</option>
                <option value="VOID">Void</option>
              </select>
            </div>
            <div className="filter">
              <label htmlFor="docs-from">Дата с</label>
              <input
                id="docs-from"
                type="date"
                value={documentsFilters.from}
                onChange={(event) => setDocumentsFilters((prev) => ({ ...prev, from: event.target.value }))}
              />
            </div>
            <div className="filter">
              <label htmlFor="docs-to">Дата по</label>
              <input
                id="docs-to"
                type="date"
                value={documentsFilters.to}
                onChange={(event) => setDocumentsFilters((prev) => ({ ...prev, to: event.target.value }))}
              />
            </div>
          </div>
          {documentsState.error ? <div className="muted">{documentsState.error}</div> : null}
        </section>
      ) : null}
      {toast ? <Toast toast={toast} onClose={() => showToast(null)} /> : null}
    </div>
  );
}
