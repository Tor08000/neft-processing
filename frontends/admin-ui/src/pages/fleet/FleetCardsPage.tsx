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
      setError({ title: "Не удалось загрузить карты", description: summary.message, details: summary.details });
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    void loadCards();
  }, [loadCards]);

  const filteredCards = useMemo(() => filterCards(cards, statusFilter, search), [cards, statusFilter, search]);

  const columns: DataColumn<FleetCard>[] = [
    { key: "card_alias", title: "Alias", render: (row) => row.card_alias ?? "—" },
    { key: "masked_pan", title: "Masked PAN", render: (row) => row.masked_pan ?? "—" },
    { key: "status", title: "Status", render: (row) => (row.status ? <StatusBadge status={row.status} /> : "—") },
    { key: "currency", title: "Currency", render: (row) => row.currency ?? "—" },
    { key: "issued_at", title: "Issued", render: (row) => formatDateTime(row.issued_at) },
    { key: "created_at", title: "Created", render: (row) => formatDateTime(row.created_at) },
  ];

  if (loading) {
    return <Loader label="Загружаем карты" />;
  }

  if (isForbidden) {
    return <ForbiddenPage />;
  }

  if (unavailable) {
    return <div className="card">Fleet cards endpoint unavailable in this environment.</div>;
  }

  return (
    <div>
      <div className="page-header">
        <h1>Fleet · Cards</h1>
      </div>
      <div className="filters">
        <div className="filter">
          <span className="label">Status</span>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="">Все</option>
            <option value="ACTIVE">ACTIVE</option>
            <option value="BLOCKED">BLOCKED</option>
          </select>
        </div>
        <div className="filter">
          <span className="label">Search</span>
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Alias, masked pan, card id"
          />
        </div>
      </div>
      <DataTable
        data={filteredCards}
        columns={columns}
        loading={false}
        errorState={error ? { title: error.title, description: error.description, details: error.details } : undefined}
        emptyState={{
          title: "Карты не найдены",
          description: "Проверьте фильтры или добавьте новую карту в клиентском кабинете.",
        }}
      />
    </div>
  );
};

export default FleetCardsPage;
