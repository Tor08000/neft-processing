import { type ChangeEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchOperations } from "../api/operations";
import { fetchCards } from "../api/cards";
import { useAuth } from "../auth/AuthContext";
import type { OperationSummary } from "../types/operations";
import type { ClientCard } from "../types/cards";
import { formatDateTime, formatLiters, formatMoney } from "../utils/format";

const STATUS_OPTIONS = [
  { value: "", label: "Все" },
  { value: "APPROVED", label: "Approved" },
  { value: "DECLINED", label: "Declined" },
];

export function OperationsPage() {
  const { user } = useAuth();
  const [operations, setOperations] = useState<OperationSummary[]>([]);
  const [cards, setCards] = useState<ClientCard[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCardsLoading, setIsCardsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState({
    status: "",
    cardId: "",
    from: "",
    to: "",
  });
  const [pagination, setPagination] = useState({ limit: 10, offset: 0 });

  useEffect(() => {
    setIsCardsLoading(true);
    fetchCards(user)
      .then((resp) => setCards(resp.items))
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsCardsLoading(false));
  }, [user]);

  useEffect(() => {
    setIsLoading(true);
    fetchOperations(user, {
      status: filters.status || undefined,
      cardId: filters.cardId || undefined,
      from: filters.from || undefined,
      to: filters.to || undefined,
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
    setFilters((prev) => ({ ...prev, [name]: value }));
  };

  if (error) {
    return (
      <div className="card error" role="alert">
        {error}
      </div>
    );
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
          <label htmlFor="status">Статус</label>
          <select id="status" name="status" value={filters.status} onChange={handleFilterChange}>
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="muted">Загружаем операции...</div>
      ) : operations.length === 0 ? (
        <p className="muted">Операций пока нет.</p>
      ) : (
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
                    <Link to={`/operations/${op.id}`} className="ghost">
                      Подробнее
                    </Link>
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
      )}
    </div>
  );
}
