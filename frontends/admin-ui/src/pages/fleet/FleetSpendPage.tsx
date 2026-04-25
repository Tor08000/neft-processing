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
import { fleetSpendPageCopy } from "./fleetPageCopy";

const formatAmount = (value?: number | string | null) => {
  if (value === undefined || value === null || value === "") return fleetSpendPageCopy.values.fallback;
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
      setError({
        title: fleetSpendPageCopy.errors.referenceLoad,
        description: summaryError.message,
        details: summaryError.details,
      });
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
      setError({
        title: fleetSpendPageCopy.errors.spendLoad,
        description: summaryError.message,
        details: summaryError.details,
      });
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
    { key: "occurred_at", title: fleetSpendPageCopy.columns.date, render: (row) => formatDateTime(row.occurred_at ?? row.created_at) },
    { key: "amount", title: fleetSpendPageCopy.columns.amount, render: (row) => formatAmount(row.amount) },
    { key: "card_id", title: fleetSpendPageCopy.columns.cardId, render: (row) => row.card_id ?? fleetSpendPageCopy.values.fallback },
    { key: "merchant_name", title: fleetSpendPageCopy.columns.merchant, render: (row) => row.merchant_name ?? fleetSpendPageCopy.values.fallback },
    { key: "category", title: fleetSpendPageCopy.columns.category, render: (row) => row.category ?? fleetSpendPageCopy.values.fallback },
    { key: "station_id", title: fleetSpendPageCopy.columns.station, render: (row) => row.station_id ?? fleetSpendPageCopy.values.fallback },
  ];
  const filtersActive = Boolean(filters.dateFrom || filters.dateTo || filters.groupId || filters.cardId || filters.groupBy !== "day");

  if (loading) {
    return <Loader label={fleetSpendPageCopy.loading} />;
  }

  if (isForbidden) {
    return <ForbiddenPage />;
  }

  if (unavailable) {
    return <div className="card">{fleetSpendPageCopy.unavailable}</div>;
  }

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div className="page-header">
        <h1>{fleetSpendPageCopy.title}</h1>
      </div>
      <div className="card">
        <h3>{fleetSpendPageCopy.summaryTitle}</h3>
        {summary?.rows?.length ? (
          <table className="table neft-table">
            <thead>
              <tr>
                <th>{fleetSpendPageCopy.summary.period}</th>
                <th>{fleetSpendPageCopy.summary.amount}</th>
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
          <EmptyState
            title={fleetSpendPageCopy.summary.emptyTitle}
            description={fleetSpendPageCopy.summary.emptyDescription}
          />
        )}
      </div>

      <div className="card">
        <h3>{fleetSpendPageCopy.transactionsTitle}</h3>
        <DataTable
          data={transactions}
          columns={transactionsColumns}
          loading={false}
          toolbar={
            <div className="table-toolbar">
              <div className="filters">
                <div className="filter">
                  <span className="label">{fleetSpendPageCopy.filters.dateFrom}</span>
                  <input
                    type="date"
                    value={filters.dateFrom}
                    onChange={(event) => setFilters((prev) => ({ ...prev, dateFrom: event.target.value }))}
                  />
                </div>
                <div className="filter">
                  <span className="label">{fleetSpendPageCopy.filters.dateTo}</span>
                  <input
                    type="date"
                    value={filters.dateTo}
                    onChange={(event) => setFilters((prev) => ({ ...prev, dateTo: event.target.value }))}
                  />
                </div>
                <div className="filter">
                  <span className="label">{fleetSpendPageCopy.filters.group}</span>
                  <select
                    value={filters.groupId}
                    onChange={(event) => setFilters((prev) => ({ ...prev, groupId: event.target.value }))}
                  >
                    <option value="">{fleetSpendPageCopy.filters.all}</option>
                    {groups.map((group) => (
                      <option key={group.id} value={group.id}>
                        {group.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="filter">
                  <span className="label">{fleetSpendPageCopy.filters.card}</span>
                  <select
                    value={filters.cardId}
                    onChange={(event) => setFilters((prev) => ({ ...prev, cardId: event.target.value }))}
                  >
                    <option value="">{fleetSpendPageCopy.filters.all}</option>
                    {cards.map((card) => (
                      <option key={card.id} value={card.id}>
                        {card.card_alias ?? card.masked_pan ?? card.id}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="filter">
                  <span className="label">{fleetSpendPageCopy.filters.groupBy}</span>
                  <select
                    value={filters.groupBy}
                    onChange={(event) => setFilters((prev) => ({ ...prev, groupBy: event.target.value }))}
                  >
                    <option value="day">{fleetSpendPageCopy.filters.day}</option>
                    <option value="week">{fleetSpendPageCopy.filters.week}</option>
                    <option value="month">{fleetSpendPageCopy.filters.month}</option>
                  </select>
                </div>
              </div>
              <div className="toolbar-actions">
                <button
                  type="button"
                  className="button secondary"
                  onClick={() =>
                    setFilters({
                      dateFrom: "",
                      dateTo: "",
                      groupId: "",
                      cardId: "",
                      groupBy: "day",
                    })
                  }
                  disabled={!filtersActive}
                >
                  {fleetSpendPageCopy.actions.reset}
                </button>
                <button type="button" className="button secondary" onClick={() => void loadSpend()}>
                  {fleetSpendPageCopy.actions.refresh}
                </button>
              </div>
            </div>
          }
          errorState={
            error
              ? {
                  title: error.title,
                  description: error.description,
                  details: error.details,
                  actionLabel: fleetSpendPageCopy.actions.retry,
                  actionOnClick: () => void loadSpend(),
                }
              : undefined
          }
          footer={
            <div className="table-footer__content muted">{fleetSpendPageCopy.footer.rows(transactions.length)}</div>
          }
          emptyState={{
            title: fleetSpendPageCopy.empty.title,
            description: fleetSpendPageCopy.empty.description,
          }}
        />
      </div>
    </div>
  );
};

export default FleetSpendPage;
