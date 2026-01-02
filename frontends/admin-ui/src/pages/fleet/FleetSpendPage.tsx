import { useCallback, useEffect, useMemo, useState } from "react";
import { getFleetSpendSummary, listFleetCards, listFleetGroups, listFleetTransactions } from "../../api/fleet";
import { useAuth } from "../../auth/AuthContext";
import { DataTable, type DataColumn } from "../../components/common/DataTable";
import { EmptyState } from "../../components/common/EmptyState";
import { Loader } from "../../components/Loader/Loader";
import ForbiddenPage from "../ForbiddenPage";
import type { FleetCard, FleetGroup, FleetSpendSummary, FleetTransaction } from "../../types/fleet";
import { describeError } from "../../utils/apiErrors";
import { formatDate, formatDateTime, formatRub } from "../../utils/format";

const formatAmount = (value?: number | string | null) => {
  if (value === undefined || value === null || value === "") return "—";
  const parsed = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(parsed)) return String(value);
  return formatRub(parsed);
};

export const FleetSpendPage = () => {
  const { accessToken } = useAuth();
  const [cards, setCards] = useState<FleetCard[]>([]);
  const [groups, setGroups] = useState<FleetGroup[]>([]);
  const [summary, setSummary] = useState<FleetSpendSummary | null>(null);
  const [transactions, setTransactions] = useState<FleetTransaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [isForbidden, setIsForbidden] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [error, setError] = useState<{ title: string; description?: string; details?: string } | null>(null);

  const [filters, setFilters] = useState({
    dateFrom: "",
    dateTo: "",
    groupId: "",
    cardId: "",
    groupBy: "day",
  });

  const filterPayload = useMemo(
    () => ({
      date_from: filters.dateFrom || undefined,
      date_to: filters.dateTo || undefined,
      group_id: filters.groupId || undefined,
      card_id: filters.cardId || undefined,
      group_by: filters.groupBy || undefined,
    }),
    [filters],
  );

  const loadReference = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    setIsForbidden(false);
    setUnavailable(false);
    setError(null);
    try {
      const [groupsResponse, cardsResponse] = await Promise.all([
        listFleetGroups(accessToken),
        listFleetCards(accessToken),
      ]);
      if (groupsResponse.unavailable || cardsResponse.unavailable) {
        setUnavailable(true);
        return;
      }
      setGroups(groupsResponse.items);
      setCards(cardsResponse.items);
    } catch (err) {
      const summaryError = describeError(err);
      if (summaryError.isForbidden) {
        setIsForbidden(true);
        return;
      }
      setError({ title: "Не удалось загрузить справочники", description: summaryError.message, details: summaryError.details });
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  const loadSpend = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    setIsForbidden(false);
    setUnavailable(false);
    setError(null);
    try {
      const [summaryResponse, transactionsResponse] = await Promise.all([
        getFleetSpendSummary(accessToken, filterPayload),
        listFleetTransactions(accessToken, filterPayload),
      ]);
      if (summaryResponse.unavailable || transactionsResponse.unavailable) {
        setUnavailable(true);
        return;
      }
      setSummary(summaryResponse);
      setTransactions(transactionsResponse.items);
    } catch (err) {
      const summaryError = describeError(err);
      if (summaryError.isForbidden) {
        setIsForbidden(true);
        return;
      }
      setError({ title: "Не удалось загрузить расходы", description: summaryError.message, details: summaryError.details });
    } finally {
      setLoading(false);
    }
  }, [accessToken, filterPayload]);

  useEffect(() => {
    void loadReference();
  }, [loadReference]);

  useEffect(() => {
    void loadSpend();
  }, [loadSpend]);

  const transactionsColumns: DataColumn<FleetTransaction>[] = [
    { key: "occurred_at", title: "Дата", render: (row) => formatDateTime(row.occurred_at ?? row.created_at) },
    { key: "amount", title: "Сумма", render: (row) => formatAmount(row.amount) },
    { key: "card_id", title: "Card ID", render: (row) => row.card_id ?? "—" },
    { key: "merchant_name", title: "Merchant", render: (row) => row.merchant_name ?? "—" },
    { key: "category", title: "Category", render: (row) => row.category ?? "—" },
    { key: "station_id", title: "Station", render: (row) => row.station_id ?? "—" },
  ];

  if (loading) {
    return <Loader label="Загружаем расходы" />;
  }

  if (isForbidden) {
    return <ForbiddenPage />;
  }

  if (unavailable) {
    return <div className="card">Fleet spend endpoint unavailable in this environment.</div>;
  }

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div className="page-header">
        <h1>Fleet · Spend</h1>
      </div>
      <div className="card">
        <div className="filters">
          <div className="filter">
            <span className="label">Date from</span>
            <input
              type="date"
              value={filters.dateFrom}
              onChange={(event) => setFilters((prev) => ({ ...prev, dateFrom: event.target.value }))}
            />
          </div>
          <div className="filter">
            <span className="label">Date to</span>
            <input
              type="date"
              value={filters.dateTo}
              onChange={(event) => setFilters((prev) => ({ ...prev, dateTo: event.target.value }))}
            />
          </div>
          <div className="filter">
            <span className="label">Group</span>
            <select
              value={filters.groupId}
              onChange={(event) => setFilters((prev) => ({ ...prev, groupId: event.target.value }))}
            >
              <option value="">Все</option>
              {groups.map((group) => (
                <option key={group.id} value={group.id}>
                  {group.name}
                </option>
              ))}
            </select>
          </div>
          <div className="filter">
            <span className="label">Card</span>
            <select
              value={filters.cardId}
              onChange={(event) => setFilters((prev) => ({ ...prev, cardId: event.target.value }))}
            >
              <option value="">Все</option>
              {cards.map((card) => (
                <option key={card.id} value={card.id}>
                  {card.card_alias ?? card.masked_pan ?? card.id}
                </option>
              ))}
            </select>
          </div>
          <div className="filter">
            <span className="label">Group by</span>
            <select
              value={filters.groupBy}
              onChange={(event) => setFilters((prev) => ({ ...prev, groupBy: event.target.value }))}
            >
              <option value="day">Day</option>
              <option value="week">Week</option>
              <option value="month">Month</option>
            </select>
          </div>
        </div>
        <div className="actions">
          <button type="button" className="secondary" onClick={() => void loadSpend()}>
            Обновить
          </button>
        </div>
        {error ? <div className="card" style={{ marginTop: 12 }}>{error.description}</div> : null}
      </div>

      <div className="card">
        <h3>Summary</h3>
        {summary?.rows?.length ? (
          <table className="table neft-table">
            <thead>
              <tr>
                <th>Period</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {summary.rows.map((row) => (
                <tr key={row.key}>
                  <td>{formatDate(row.key)}</td>
                  <td>{formatAmount(row.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <EmptyState title="Нет данных по расходам" description="Проверьте фильтры или выберите другой период." />
        )}
      </div>

      <div className="card">
        <h3>Transactions</h3>
        <DataTable
          data={transactions}
          columns={transactionsColumns}
          loading={false}
          errorState={error ? { title: error.title, description: error.description, details: error.details } : undefined}
          emptyState={{
            title: "Транзакции не найдены",
            description: "В выбранном периоде нет операций по топливным картам.",
          }}
        />
      </div>
    </div>
  );
};

export default FleetSpendPage;
