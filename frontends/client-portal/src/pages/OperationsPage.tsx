import { type ChangeEvent, useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { fetchOperations } from "../api/operations";
import { fetchCards } from "../api/cards";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { ClientErrorState } from "../components/ClientErrorState";
import { AppForbiddenState } from "../components/states";
import { Table } from "../components/common/Table";
import { demoOperations } from "../demo/demoData";
import type { OperationSummary } from "../types/operations";
import type { ClientCard } from "../types/cards";
import { formatDateTime, formatLiters } from "../utils/format";
import { MoneyValue } from "../components/common/MoneyValue";
import { canAccessOps } from "../utils/roles";
import { isDemoClient } from "@shared/demo/demo";

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
const DEFAULT_FILTERS = {
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
};

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
  const [error, setError] = useState<{ message: string; status?: number; details?: string } | null>(null);
  const [useDemoData, setUseDemoData] = useState(false);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [pagination, setPagination] = useState({ limit: 10, offset: 0 });
  const [savedFilters, setSavedFilters] = useState<Record<string, typeof filters>>({});
  const isDemoClientAccount = isDemoClient(user?.email ?? null);

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
      .catch((err: Error) => {
        console.error("Не удалось загрузить карты", err);
        if (isDemoClientAccount) {
          setCards([]);
          return;
        }
        setError({ message: "Не удалось загрузить карты.", details: err.message });
      })
      .finally(() => setIsCardsLoading(false));
  }, [user, isDemoClientAccount]);

  useEffect(() => {
    if (!user) return;
    setIsLoading(true);
    setUseDemoData(false);
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
      .catch((err: unknown) => {
        console.error("Не удалось загрузить операции", err);
        if (isDemoClientAccount) {
          setOperations(demoOperations);
          setTotal(demoOperations.length);
          setUseDemoData(true);
          return;
        }
        if (err instanceof ApiError) {
          setError({ message: "Не удалось загрузить операции.", status: err.status, details: err.message });
          return;
        }
        setError({ message: "Не удалось загрузить операции.", details: err instanceof Error ? err.message : String(err) });
      })
      .finally(() => setIsLoading(false));
  }, [user, filters, pagination, isDemoClientAccount]);

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

  const filtersActive = Object.entries(filters).some(([key, value]) => value !== DEFAULT_FILTERS[key as keyof typeof DEFAULT_FILTERS]);

  const handleResetFilters = () => {
    setFilters(DEFAULT_FILTERS);
    setPagination((prev) => ({ ...prev, offset: 0 }));
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
          <p className="muted">
            {useDemoData
              ? "Демо-режим: операции сформированы на основе типового сценария."
              : "Расходы по топливу, статусы и детали транзакций."}
          </p>
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
          <button type="button" className="secondary neft-btn-secondary" onClick={handleSaveFilters}>
            Сохранить фильтр
          </button>
        </div>
        <div className="filter">
          <button type="button" className="secondary neft-btn-secondary" onClick={handleResetFilters} disabled={!filtersActive}>
            Сбросить
          </button>
        </div>
      </div>

      {useDemoData ? <div className="notice">Фильтры работают в демо-режиме, данные обновляются локально.</div> : null}
      {error ? (
        <ClientErrorState
          title="Расходы недоступны"
          description="Не удалось загрузить операции. Попробуйте обновить страницу."
          details={error.details}
          onRetry={() => setFilters((prev) => ({ ...prev }))}
        />
      ) : null}
      {!error ? (
        <>
          <Table
            data={operations}
            loading={isLoading}
            columns={[
              { key: "created_at", title: "Дата/время", render: (op) => formatDateTime(op.created_at) },
              { key: "card", title: "Карта", render: (op) => op.card_id },
              { key: "merchant", title: "АЗС", render: (op) => op.merchant_id ?? "—" },
              { key: "product", title: "Продукт", render: (op) => op.product_type ?? "—" },
              { key: "liters", title: "Литры", className: "neft-num", render: (op) => formatLiters(op.quantity) },
              {
                key: "amount",
                title: "Сумма",
                className: "neft-num",
                render: (op) => <MoneyValue amount={op.amount} currency={op.currency} />,
              },
              {
                key: "status",
                title: "Статус",
                render: (op) => {
                  const statusTone = op.status === "APPROVED" ? "ok" : op.status === "DECLINED" ? "err" : "warn";
                  return (
                    <div>
                      <span className={`neft-chip neft-chip-${statusTone}`}>{op.status}</span>
                      {op.status === "DECLINED" && op.reason && <div className="muted small">{op.reason}</div>}
                    </div>
                  );
                },
              },
              {
                key: "reason",
                title: "Причина",
                render: (op) =>
                  op.primary_reason ? (
                    <span className="neft-chip neft-chip-muted" title={op.primary_reason}>
                      {op.primary_reason}
                    </span>
                  ) : (
                    op.reason ?? "—"
                  ),
              },
              {
                key: "risk",
                title: "Risk",
                render: (op) =>
                  op.risk_level ? (
                    <span className="neft-chip neft-chip-warn" title={`Risk score: ${op.risk_level}`}>
                      {op.risk_level}
                    </span>
                  ) : (
                    "—"
                  ),
              },
              {
                key: "actions",
                title: "",
                render: (op) => (
                  <div className="actions">
                    <Link to={`/operations/${op.id}`} className="ghost">
                      Подробнее
                    </Link>
                    <Link to={`/explain?kind=operation&id=${encodeURIComponent(op.id)}`} className="ghost">
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
                ),
              },
            ]}
            emptyState={{
              title: "Операций пока нет",
              description: filtersActive ? "Сбросьте фильтры или измените период." : "Попробуйте обновить список позже.",
              actionLabel: filtersActive ? "Сбросить фильтры" : "Обновить",
              actionOnClick: filtersActive ? handleResetFilters : () => setPagination((prev) => ({ ...prev })),
            }}
          />

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
