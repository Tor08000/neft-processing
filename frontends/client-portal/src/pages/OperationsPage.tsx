import { type ChangeEvent, useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { fetchOperations } from "../api/operations";
import { fetchCards } from "../api/cards";
import { useAuth } from "../auth/AuthContext";
import { AppEmptyState, AppErrorState, AppForbiddenState, AppLoadingState } from "../components/states";
import type { OperationSummary } from "../types/operations";
import type { ClientCard } from "../types/cards";
import { formatDateTime, formatLiters, formatMoney } from "../utils/format";
import { canAccessOps } from "../utils/roles";

const STATUS_OPTIONS = [
  { value: "", label: "Все" },
  { value: "APPROVED", label: "Approved" },
  { value: "DECLINED", label: "Declined" },
  { value: "SETTLED", label: "Settled" },
];

const PERIOD_PRESETS = [
  { value: "today", label: "Сегодня" },
  { value: "7d", label: "7 дней" },
  { value: "30d", label: "30 дней" },
  { value: "custom", label: "Выбрать" },
];

const FILTERS_STORAGE = "client-ops-filters";

const buildDateRange = (preset: string) => {
  const to = new Date();
  const from = new Date();
  if (preset === "today") {
    from.setHours(0, 0, 0, 0);
  } else if (preset === "7d") {
    from.setDate(to.getDate() - 7);
  } else if (preset === "30d") {
    from.setDate(to.getDate() - 30);
  }
  return { from: from.toISOString().slice(0, 10), to: to.toISOString().slice(0, 10) };
};

export function OperationsPage() {
  const { user } = useAuth();
  const location = useLocation();
  const [operations, setOperations] = useState<OperationSummary[]>([]);
  const [cards, setCards] = useState<ClientCard[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCardsLoading, setIsCardsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState({
    preset: "30d",
    status: "",
    cardId: "",
    from: "",
    to: "",
    merchantId: "",
    productType: "",
    driverId: "",
    vehicleId: "",
    minAmount: "",
    maxAmount: "",
  });
  const [pagination, setPagination] = useState({ limit: 10, offset: 0 });
  const [savedFilters, setSavedFilters] = useState<Record<string, typeof filters>>({});

  useEffect(() => {
    const stored = localStorage.getItem(FILTERS_STORAGE);
    if (stored) {
      try {
        setSavedFilters(JSON.parse(stored));
      } catch {
        setSavedFilters({});
      }
    }
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const from = params.get("from") ?? "";
    const to = params.get("to") ?? "";
    const status = params.get("status") ?? "";
    if (from || to || status) {
      setFilters((prev) => ({ ...prev, from, to, status, preset: "custom" }));
    }
  }, [location.search]);

  useEffect(() => {
    if (!user) return;
    setIsCardsLoading(true);
    fetchCards(user)
      .then((resp) => setCards(resp.items))
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsCardsLoading(false));
  }, [user]);

  useEffect(() => {
    if (!user) return;
    setIsLoading(true);
    fetchOperations(user, {
      status: filters.status || undefined,
      cardId: filters.cardId || undefined,
      from: filters.from || undefined,
      to: filters.to || undefined,
      merchantId: filters.merchantId || undefined,
      productType: filters.productType || undefined,
      driverId: filters.driverId || undefined,
      vehicleId: filters.vehicleId || undefined,
      minAmount: filters.minAmount || undefined,
      maxAmount: filters.maxAmount || undefined,
      limit: pagination.limit,
      offset: pagination.offset,
    })
      .then((resp) => {
        setOperations(resp.items);
        setTotal(resp.total);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [user, filters, pagination]);

  const pageNumber = useMemo(
    () => Math.floor(pagination.offset / pagination.limit) + 1,
    [pagination.offset, pagination.limit],
  );
  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / pagination.limit)),
    [pagination.limit, total],
  );

  const handleFilterChange = (evt: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = evt.target;
    setPagination((prev) => ({ ...prev, offset: 0 }));
    setFilters((prev) => ({ ...prev, [name]: value, preset: name === "preset" ? value : prev.preset }));
  };

  const handlePresetChange = (preset: string) => {
    if (preset === "custom") {
      setFilters((prev) => ({ ...prev, preset }));
      return;
    }
    const range = buildDateRange(preset);
    setFilters((prev) => ({ ...prev, ...range, preset }));
  };

  const handleSaveFilters = () => {
    const name = window.prompt("Название фильтра");
    if (!name) return;
    const next = { ...savedFilters, [name]: filters };
    setSavedFilters(next);
    localStorage.setItem(FILTERS_STORAGE, JSON.stringify(next));
  };

  const handleApplySaved = (name: string) => {
    const saved = savedFilters[name];
    if (saved) {
      setFilters(saved);
      setPagination((prev) => ({ ...prev, offset: 0 }));
    }
  };

  if (!user) {
    return <AppForbiddenState message="Нет доступа к операциям." />;
  }

  if (!canAccessOps(user)) {
    return <AppForbiddenState message="Недостаточно прав для просмотра операций." />;
  }

  return (
    <div className="card">
      <div className="card__header">
        <div>
          <h2>Операции</h2>
          <p className="muted">Расходы по топливу, статусы и детали транзакций.</p>
        </div>
      </div>

      <div className="filters">
        <div className="filter">
          <label htmlFor="preset">Период</label>
          <select
            id="preset"
            name="preset"
            value={filters.preset}
            onChange={(event) => handlePresetChange(event.target.value)}
          >
            {PERIOD_PRESETS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        <div className="filter">
          <label htmlFor="from">Период с</label>
          <input id="from" name="from" type="date" value={filters.from} onChange={handleFilterChange} />
        </div>
        <div className="filter">
          <label htmlFor="to">Период по</label>
          <input id="to" name="to" type="date" value={filters.to} onChange={handleFilterChange} />
        </div>
        <div className="filter">
          <label htmlFor="cardId">Карта</label>
          <select
            id="cardId"
            name="cardId"
            value={filters.cardId}
            onChange={handleFilterChange}
            disabled={isCardsLoading}
          >
            <option value="">Все</option>
            {cards.map((card) => (
              <option key={card.id} value={card.id}>
                {card.pan_masked ?? card.id}
              </option>
            ))}
          </select>
        </div>
        <div className="filter">
          <label htmlFor="merchantId">Станция/мерчант</label>
          <input
            id="merchantId"
            name="merchantId"
            type="text"
            placeholder="ID мерчанта"
            value={filters.merchantId}
            onChange={handleFilterChange}
          />
        </div>
        <div className="filter">
          <label htmlFor="vehicleId">ТС/Vehicle</label>
          <input
            id="vehicleId"
            name="vehicleId"
            type="text"
            placeholder="ID транспорта"
            value={filters.vehicleId}
            onChange={handleFilterChange}
          />
        </div>
        <div className="filter">
          <label htmlFor="driverId">Driver</label>
          <input
            id="driverId"
            name="driverId"
            type="text"
            placeholder="ID водителя"
            value={filters.driverId}
            onChange={handleFilterChange}
          />
        </div>
        <div className="filter">
          <label htmlFor="productType">Продукт</label>
          <input
            id="productType"
            name="productType"
            type="text"
            placeholder="Тип топлива"
            value={filters.productType}
            onChange={handleFilterChange}
          />
        </div>
        <div className="filter">
          <label htmlFor="status">Статус</label>
          <select id="status" name="status" value={filters.status} onChange={handleFilterChange}>
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        <div className="filter">
          <label htmlFor="minAmount">Сумма от</label>
          <input
            id="minAmount"
            name="minAmount"
            type="number"
            min="0"
            value={filters.minAmount}
            onChange={handleFilterChange}
          />
        </div>
        <div className="filter">
          <label htmlFor="maxAmount">Сумма до</label>
          <input
            id="maxAmount"
            name="maxAmount"
            type="number"
            min="0"
            value={filters.maxAmount}
            onChange={handleFilterChange}
          />
        </div>
        <div className="filter">
          <label htmlFor="savedFilters">Saved filters</label>
          <select id="savedFilters" onChange={(event) => handleApplySaved(event.target.value)} value="">
            <option value="">—</option>
            {Object.keys(savedFilters).map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </div>
        <div className="filter">
          <button type="button" className="secondary" onClick={handleSaveFilters}>
            Сохранить фильтр
          </button>
        </div>
      </div>

      {isLoading ? <AppLoadingState /> : null}
      {error ? <AppErrorState message={error} /> : null}
      {!isLoading && !error && operations.length === 0 ? (
        <AppEmptyState title="Операций пока нет" description="Проверьте фильтры или период." />
      ) : null}
      {!isLoading && !error && operations.length > 0 ? (
        <>
          <table className="table">
            <thead>
              <tr>
                <th>Дата/время</th>
                <th>Карта</th>
                <th>АЗС</th>
                <th>Продукт</th>
                <th>Литры</th>
                <th>Сумма</th>
                <th>Статус</th>
                <th>Причина</th>
                <th>Risk</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {operations.map((op) => (
                <tr key={op.id}>
                  <td>{formatDateTime(op.created_at)}</td>
                  <td>{op.card_id}</td>
                  <td>{op.merchant_id ?? "—"}</td>
                  <td>{op.product_type ?? "—"}</td>
                  <td>{formatLiters(op.quantity)}</td>
                  <td>{formatMoney(op.amount, op.currency)}</td>
                  <td>
                    <span className={`pill pill--${op.status === "APPROVED" ? "success" : "warning"}`}>
                      {op.status}
                    </span>
                    {op.status === "DECLINED" && op.reason && <div className="muted small">{op.reason}</div>}
                  </td>
                  <td>
                    {op.primary_reason ? (
                      <span className="pill pill--neutral">{op.primary_reason}</span>
                    ) : (
                      op.reason ?? "—"
                    )}
                  </td>
                  <td>{op.risk_level ? <span className="pill pill--warning">{op.risk_level}</span> : "—"}</td>
                  <td>
                    <div className="actions">
                      <Link to={`/operations/${op.id}`} className="ghost">
                        Подробнее
                      </Link>
                      <Link to={`/explain/${op.id}`} className="ghost">
                        Explain
                      </Link>
                      {op.document_ids?.length ? (
                        <Link to={`/documents/${op.document_ids[0]}`} className="ghost">
                          Open linked docs
                        </Link>
                      ) : (
                        <button type="button" className="ghost" disabled>
                          Open linked docs
                        </button>
                      )}
                      <button type="button" className="ghost" disabled>
                        Open money flow summary
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="pagination">
            <button
              type="button"
              className="secondary"
              onClick={() =>
                setPagination((prev) => ({ ...prev, offset: Math.max(0, prev.offset - prev.limit) }))
              }
              disabled={pagination.offset === 0 || isLoading}
            >
              Назад
            </button>
            <span className="muted">
              Страница {pageNumber} из {totalPages}
            </span>
            <button
              type="button"
              className="secondary"
              onClick={() =>
                setPagination((prev) => ({ ...prev, offset: prev.offset + prev.limit }))
              }
              disabled={pagination.offset + pagination.limit >= total || isLoading}
            >
              Далее
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}
