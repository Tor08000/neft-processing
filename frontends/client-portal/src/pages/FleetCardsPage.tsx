import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import { Table } from "../components/common/Table";
import type { Column } from "../components/common/Table";
import { StatusBadge } from "../components/StatusBadge";
import { AppForbiddenState } from "../components/states";
import { FleetUnavailableState } from "../components/FleetUnavailableState";
import { useToast } from "../components/Toast/useToast";
import { Toast } from "../components/Toast/Toast";
import { listCards, createCard, blockCard, unblockCard } from "../api/fleet";
import type { FleetCard } from "../types/fleet";
import { ApiError } from "../api/http";
import { formatDateTime } from "../utils/format";
import { canManageFleetCards } from "../utils/fleetPermissions";

const maskedPanPattern = /^\d{6}\*{6}\d{4}$/;

const generateShortId = () => {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID().split("-")[0];
  }
  return Math.random().toString(36).slice(2, 10);
};

export function FleetCardsPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const { toast, showToast } = useToast();
  const [cards, setCards] = useState<FleetCard[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isForbidden, setIsForbidden] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [alias, setAlias] = useState("");
  const [maskedPan, setMaskedPan] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const canManage = canManageFleetCards(user);

  const loadCards = useCallback(async () => {
    if (!user?.token) return;
    setLoading(true);
    setError(null);
    setIsForbidden(false);
    setUnavailable(false);
    try {
      const response = await listCards(user.token);
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      setCards(response.items);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setIsForbidden(true);
        return;
      }
      setError(err instanceof Error ? err.message : t("fleet.errors.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [t, user?.token]);

  useEffect(() => {
    void loadCards();
  }, [loadCards]);

  const filteredCards = useMemo(() => {
    const term = search.trim().toLowerCase();
    return cards.filter((card) => {
      const statusOk = statusFilter ? card.status === statusFilter : true;
      const aliasValue = card.card_alias ?? "";
      const maskedValue = card.masked_pan ?? "";
      const searchOk = term
        ? aliasValue.toLowerCase().includes(term) || maskedValue.toLowerCase().includes(term)
        : true;
      return statusOk && searchOk;
    });
  }, [cards, statusFilter, search]);

  const handleToggleStatus = useCallback(
    async (card: FleetCard) => {
      if (!user?.token) return;
      const action = card.status === "BLOCKED" ? unblockCard : blockCard;
      try {
        const response = await action(user.token, card.id);
        if (response.unavailable) {
          setUnavailable(true);
          return;
        }
        if (response.item) {
          setCards((prev) => prev.map((item) => (item.id === card.id ? response.item ?? item : item)));
          showToast({ kind: "success", text: t("fleet.cards.updated") });
        }
      } catch (err) {
        showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleet.errors.actionFailed") });
      }
    },
    [showToast, t, user?.token],
  );

  const handleOpenAdd = () => {
    setAlias("");
    setMaskedPan("");
    setFormError(null);
    setShowAddModal(true);
  };

  const handleCreateCard = async () => {
    if (!user?.token) return;
    const aliasValue = alias.trim() || `card-${generateShortId()}`;
    if (!maskedPanPattern.test(maskedPan.trim())) {
      setFormError(t("fleet.cards.maskedPanError"));
      return;
    }
    setFormError(null);
    try {
      const response = await createCard(user.token, { card_alias: aliasValue, masked_pan: maskedPan.trim() });
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      if (response.item) {
        setCards((prev) => [response.item!, ...prev]);
        showToast({ kind: "success", text: t("fleet.cards.created") });
        setShowAddModal(false);
      }
    } catch (err) {
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleet.errors.actionFailed") });
    }
  };

  const columns: Column<FleetCard>[] = [
    { key: "alias", title: t("fleet.cards.alias"), render: (row) => row.card_alias ?? t("common.notAvailable") },
    { key: "masked", title: t("fleet.cards.maskedPan"), render: (row) => row.masked_pan ?? t("common.notAvailable") },
    { key: "status", title: t("fleet.cards.status"), render: (row) => (row.status ? <StatusBadge status={row.status} /> : t("common.notAvailable")) },
    { key: "currency", title: t("fleet.cards.currency"), render: (row) => row.currency ?? t("common.notAvailable") },
    { key: "issued", title: t("fleet.cards.issued"), render: (row) => (row.issued_at ? formatDateTime(row.issued_at) : t("common.notAvailable")) },
    {
      key: "actions",
      title: t("fleet.cards.actions"),
      render: (row) => (
        <div className="actions">
          <Link className="ghost" to={`/fleet/cards/${row.id}`}>
            {t("common.open")}
          </Link>
          {canManage ? (
            <button type="button" className="secondary" onClick={() => void handleToggleStatus(row)}>
              {row.status === "BLOCKED" ? t("fleet.cards.unblock") : t("fleet.cards.block")}
            </button>
          ) : null}
        </div>
      ),
    },
  ];

  if (loading) {
    return (
      <div className="page">
        <div className="page-header">
          <h1>{t("fleet.cards.title")}</h1>
        </div>
        <Table columns={columns} data={[]} loading />
      </div>
    );
  }

  if (isForbidden) {
    return <AppForbiddenState message={t("fleet.errors.noPermission")} />;
  }

  if (unavailable) {
    return <FleetUnavailableState />;
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>{t("fleet.cards.title")}</h1>
        <div className="actions">
          {canManage ? (
            <button type="button" className="primary" onClick={handleOpenAdd}>
              {t("fleet.cards.add")}
            </button>
          ) : null}
          <button type="button" className="secondary" onClick={() => void loadCards()}>
            {t("actions.refresh")}
          </button>
        </div>
      </div>
      <div className="filters">
        <div className="filter">
          <span className="label">{t("fleet.cards.status")}</span>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="">{t("fleet.cards.statusAll")}</option>
            <option value="ACTIVE">{t("fleet.cards.statusActive")}</option>
            <option value="BLOCKED">{t("fleet.cards.statusBlocked")}</option>
          </select>
        </div>
        <div className="filter">
          <span className="label">{t("fleet.cards.search")}</span>
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t("fleet.cards.searchPlaceholder")}
          />
        </div>
      </div>
      {error ? <div className="card state">{error}</div> : null}
      <Table
        columns={columns}
        data={filteredCards}
        emptyState={{
          title: t("fleet.cards.emptyTitle"),
          description: t("fleet.cards.emptyDescription"),
        }}
      />
      {showAddModal ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-card">
            <h2>{t("fleet.cards.addTitle")}</h2>
            <div className="form-grid">
              <label className="form-field">
                <span>{t("fleet.cards.alias")}</span>
                <input value={alias} onChange={(event) => setAlias(event.target.value)} placeholder={t("fleet.cards.aliasPlaceholder")} />
              </label>
              <label className="form-field">
                <span>{t("fleet.cards.maskedPan")}</span>
                <input
                  value={maskedPan}
                  onChange={(event) => setMaskedPan(event.target.value)}
                  placeholder={t("fleet.cards.maskedPanPlaceholder")}
                />
              </label>
            </div>
            {formError ? <div className="error-text">{formError}</div> : null}
            <div className="actions">
              <button type="button" className="ghost" onClick={() => setShowAddModal(false)}>
                {t("actions.comeBackLater")}
              </button>
              <button type="button" className="primary" onClick={() => void handleCreateCard()}>
                {t("fleet.cards.submit")}
              </button>
            </div>
          </div>
        </div>
      ) : null}
      <Toast toast={toast} />
    </div>
  );
}
