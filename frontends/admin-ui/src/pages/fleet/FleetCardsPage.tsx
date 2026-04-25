import { useCallback, useEffect, useMemo, useState } from "react";
import { listFleetCards } from "../../api/fleet";
import { useAuth } from "../../auth/AuthContext";
import { DataTable, type DataColumn } from "../../components/common/DataTable";
import { Loader } from "../../components/Loader/Loader";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import ForbiddenPage from "../ForbiddenPage";
import type { FleetCard } from "../../types/fleet";
import { describeError } from "../../utils/apiErrors";
import { formatDateTime } from "../../utils/format";
import { fleetCardsPageCopy } from "./fleetPageCopy";

const filterCards = (cards: FleetCard[], status: string, search: string) => {
  const term = search.trim().toLowerCase();
  return cards.filter((card) => {
    const statusOk = status ? card.status === status : true;
    const alias = card.card_alias ?? "";
    const masked = card.masked_pan ?? "";
    const id = card.id ?? "";
    const searchOk = term
      ? alias.toLowerCase().includes(term) || masked.toLowerCase().includes(term) || id.toLowerCase().includes(term)
      : true;
    return statusOk && searchOk;
  });
};

export const FleetCardsPage = () => {
  const { accessToken } = useAuth();
  const [cards, setCards] = useState<FleetCard[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [isForbidden, setIsForbidden] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [error, setError] = useState<{ title: string; description?: string; details?: string } | null>(null);

  const loadCards = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    setIsForbidden(false);
    setUnavailable(false);
    setError(null);
    try {
      const response = await listFleetCards(accessToken);
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      setCards(response.items);
    } catch (err) {
      const summary = describeError(err);
      if (summary.isForbidden) {
        setIsForbidden(true);
        return;
      }
      setError({ title: fleetCardsPageCopy.errors.load, description: summary.message, details: summary.details });
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    void loadCards();
  }, [loadCards]);

  const filteredCards = useMemo(() => filterCards(cards, statusFilter, search), [cards, statusFilter, search]);
  const filtersActive = Boolean(statusFilter || search.trim());

  const columns: DataColumn<FleetCard>[] = [
    { key: "card_alias", title: fleetCardsPageCopy.columns.alias, render: (row) => row.card_alias ?? fleetCardsPageCopy.values.fallback },
    { key: "masked_pan", title: fleetCardsPageCopy.columns.maskedPan, render: (row) => row.masked_pan ?? fleetCardsPageCopy.values.fallback },
    {
      key: "status",
      title: fleetCardsPageCopy.columns.status,
      render: (row) => (row.status ? <StatusBadge status={row.status} /> : fleetCardsPageCopy.values.fallback),
    },
    { key: "currency", title: fleetCardsPageCopy.columns.currency, render: (row) => row.currency ?? fleetCardsPageCopy.values.fallback },
    { key: "issued_at", title: fleetCardsPageCopy.columns.issued, render: (row) => formatDateTime(row.issued_at) },
    { key: "created_at", title: fleetCardsPageCopy.columns.created, render: (row) => formatDateTime(row.created_at) },
  ];

  if (loading) {
    return <Loader label={fleetCardsPageCopy.loading} />;
  }

  if (isForbidden) {
    return <ForbiddenPage />;
  }

  if (unavailable) {
    return <div className="card">{fleetCardsPageCopy.unavailable}</div>;
  }

  return (
    <div>
      <div className="page-header">
        <h1>{fleetCardsPageCopy.title}</h1>
      </div>
      <DataTable
        data={filteredCards}
        columns={columns}
        loading={false}
        toolbar={
          <div className="table-toolbar">
            <div className="filters">
              <div className="filter">
                <span className="label">{fleetCardsPageCopy.filters.status}</span>
                <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                  <option value="">{fleetCardsPageCopy.filters.all}</option>
                  <option value="ACTIVE">ACTIVE</option>
                  <option value="BLOCKED">BLOCKED</option>
                </select>
              </div>
              <div className="filter filter--wide">
                <span className="label">{fleetCardsPageCopy.filters.search}</span>
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder={fleetCardsPageCopy.filters.searchPlaceholder}
                />
              </div>
            </div>
            <div className="toolbar-actions">
              <button
                type="button"
                className="button secondary"
                onClick={() => {
                  setStatusFilter("");
                  setSearch("");
                }}
                disabled={!filtersActive}
              >
                {fleetCardsPageCopy.actions.reset}
              </button>
            </div>
          </div>
        }
        errorState={error ? { title: error.title, description: error.description, details: error.details } : undefined}
        footer={<div className="table-footer__content muted">{fleetCardsPageCopy.footer.rows(filteredCards.length)}</div>}
        emptyState={{
          title: fleetCardsPageCopy.empty.title,
          description: fleetCardsPageCopy.empty.description,
          actionLabel: filtersActive ? fleetCardsPageCopy.empty.resetAction : undefined,
          actionOnClick: filtersActive
            ? () => {
                setStatusFilter("");
                setSearch("");
              }
            : undefined,
        }}
      />
    </div>
  );
};

export default FleetCardsPage;
