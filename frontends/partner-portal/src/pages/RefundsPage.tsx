import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/http";
import { fetchRefunds, type RefundFilters } from "../api/refunds";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ErrorState, ForbiddenState, LoadingState } from "../components/states";
import { StatusBadge } from "../components/StatusBadge";
import type { RefundRequest } from "../types/marketplace";
import { formatCurrency, formatDateTime } from "../utils/format";
import { canReadRefunds } from "../utils/roles";

const PAGE_SIZE = 20;

type PeriodPreset = "today" | "7d" | "30d" | "custom";

const toDateInput = (date: Date) => date.toISOString().slice(0, 10);

const startOfDay = (date: Date) => new Date(date.getFullYear(), date.getMonth(), date.getDate());

const getPresetRange = (preset: PeriodPreset) => {
  const now = new Date();
  if (preset === "today") {
    const start = startOfDay(now);
    return { from: toDateInput(start), to: toDateInput(now) };
  }
  if (preset === "7d") {
    const start = new Date(now);
    start.setDate(start.getDate() - 6);
    return { from: toDateInput(start), to: toDateInput(now) };
  }
  if (preset === "30d") {
    const start = new Date(now);
    start.setDate(start.getDate() - 29);
    return { from: toDateInput(start), to: toDateInput(now) };
  }
  return { from: "", to: "" };
};

export function RefundsPage() {
  const { user } = useAuth();
  const [refunds, setRefunds] = useState<RefundRequest[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [correlationId, setCorrelationId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState<RefundFilters>({});
  const [periodPreset, setPeriodPreset] = useState<PeriodPreset>("7d");

  const canRead = canReadRefunds(user?.roles);

  useEffect(() => {
    if (!user || !canRead) return;
    let active = true;
    const offset = String((page - 1) * PAGE_SIZE);
    const limit = String(PAGE_SIZE);
    setIsLoading(true);
    setError(null);
    setCorrelationId(null);
    fetchRefunds(user.token, { ...filters, offset, limit })
      .then((data) => {
        if (!active) return;
        setRefunds(data.items ?? []);
        setTotal(data.total ?? 0);
      })
      .catch((err) => {
        console.error(err);
        if (!active) return;
        if (err instanceof ApiError) {
          setError("Не удалось загрузить возвраты");
          setCorrelationId(null);
        } else {
          setError("Не удалось загрузить возвраты");
        }
      })
      .finally(() => {
        if (active) {
          setIsLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [user, filters, page, canRead]);

  useEffect(() => {
    if (!user) return;
    if (!filters.from && !filters.to) {
      const range = getPresetRange(periodPreset);
      setFilters((prev) => ({ ...prev, ...range }));
    }
  }, [user, periodPreset, filters.from, filters.to]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const handlePresetChange = (preset: PeriodPreset) => {
    setPeriodPreset(preset);
    if (preset !== "custom") {
      const range = getPresetRange(preset);
      setFilters((prev) => ({ ...prev, from: range.from, to: range.to }));
    }
    setPage(1);
  };

  const handleFilterChange = (key: keyof RefundFilters, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  };

  if (!canRead) {
    return <ForbiddenState />;
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <h2>Возвраты</h2>
        </div>
        <div className="filters">
          <label className="filter">
            Период
            <select value={periodPreset} onChange={(event) => handlePresetChange(event.target.value as PeriodPreset)}>
              <option value="today">Сегодня</option>
              <option value="7d">7 дней</option>
              <option value="30d">30 дней</option>
              <option value="custom">Произвольно</option>
            </select>
          </label>
          <label className="filter">
            С
            <input type="date" value={filters.from ?? ""} onChange={(event) => handleFilterChange("from", event.target.value)} />
          </label>
          <label className="filter">
            По
            <input type="date" value={filters.to ?? ""} onChange={(event) => handleFilterChange("to", event.target.value)} />
          </label>
          <label className="filter">
            Статус
            <select value={filters.status ?? ""} onChange={(event) => handleFilterChange("status", event.target.value)}>
              <option value="">Все</option>
              <option value="OPEN">OPEN</option>
              <option value="UNDER_REVIEW">UNDER_REVIEW</option>
              <option value="APPROVED">APPROVED</option>
              <option value="DENIED">DENIED</option>
              <option value="COMPLETED">COMPLETED</option>
            </select>
          </label>
          <label className="filter">
            Order ID
            <input type="text" value={filters.order_id ?? ""} onChange={(event) => handleFilterChange("order_id", event.target.value)} />
          </label>
          <label className="filter">
            Сумма от
            <input type="number" value={filters.amount_min ?? ""} onChange={(event) => handleFilterChange("amount_min", event.target.value)} />
          </label>
          <label className="filter">
            Сумма до
            <input type="number" value={filters.amount_max ?? ""} onChange={(event) => handleFilterChange("amount_max", event.target.value)} />
          </label>
        </div>

        {isLoading ? (
          <LoadingState />
        ) : error ? (
          <ErrorState
            description={error}
            correlationId={correlationId}
            action={
              <button type="button" className="secondary" onClick={() => setPage(1)}>
                Повторить
              </button>
            }
          />
        ) : refunds.length === 0 ? (
          <EmptyState title="Нет возвратов" description="Возвраты за выбранный период отсутствуют." />
        ) : (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Refund ID</th>
                  <th>Order ID</th>
                  <th>Статус</th>
                  <th>Сумма</th>
                  <th>Причина</th>
                  <th>Создан</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {refunds.map((refund) => (
                  <tr key={refund.id}>
                    <td>{refund.id}</td>
                    <td>{refund.orderId}</td>
                    <td>
                      <StatusBadge status={refund.status} />
                    </td>
                    <td>{formatCurrency(refund.amount)}</td>
                    <td>{refund.reason ?? "—"}</td>
                    <td>{formatDateTime(refund.createdAt)}</td>
                    <td>
                      <Link className="link-button" to={`/refunds/${refund.id}`}>
                        Открыть
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="pagination">
              <button type="button" className="secondary" onClick={() => setPage((prev) => Math.max(prev - 1, 1))} disabled={page <= 1}>
                Назад
              </button>
              <div className="muted">Страница {page} из {totalPages}</div>
              <button type="button" className="secondary" onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))} disabled={page >= totalPages}>
                Вперёд
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
