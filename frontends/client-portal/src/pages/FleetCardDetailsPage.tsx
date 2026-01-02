import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import { StatusBadge } from "../components/StatusBadge";
import { AppForbiddenState } from "../components/states";
import { FleetUnavailableState } from "../components/FleetUnavailableState";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";
import { Table } from "../components/common/Table";
import type { Column } from "../components/common/Table";
import type { FleetCard, FleetLimit, FleetTransaction } from "../types/fleet";
import {
  blockCard,
  getCard,
  listLimits,
  listTransactions,
  setLimit,
  unblockCard,
} from "../api/fleet";
import { ApiError } from "../api/http";
import { formatDateTime, formatLiters, formatMoney } from "../utils/format";
import { canManageFleetCards, canManageFleetLimits } from "../utils/fleetPermissions";

const defaultLimitState = {
  period: "daily",
  amount_limit: "",
  volume_limit_liters: "",
  categories: "",
  effective_from: "",
};

export function FleetCardDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const { toast, showToast } = useToast();
  const [card, setCard] = useState<FleetCard | null>(null);
  const [limits, setLimits] = useState<FleetLimit[]>([]);
  const [transactions, setTransactions] = useState<FleetTransaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isForbidden, setIsForbidden] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [showLimitModal, setShowLimitModal] = useState(false);
  const [limitForm, setLimitForm] = useState(defaultLimitState);

  const canManage = canManageFleetCards(user);
  const canManageLimits = canManageFleetLimits(user);

  const loadData = useCallback(async () => {
    if (!user?.token || !id) return;
    setLoading(true);
    setError(null);
    setIsForbidden(false);
    setUnavailable(false);
    try {
      const [cardResponse, limitsResponse, transactionsResponse] = await Promise.all([
        getCard(user.token, id),
        listLimits(user.token, { scope_type: "card", scope_id: id }),
        listTransactions(user.token, { card_id: id, page: 0, page_size: 20 }),
      ]);
      if (cardResponse.unavailable || limitsResponse.unavailable || transactionsResponse.unavailable) {
        setUnavailable(true);
        return;
      }
      setCard(cardResponse.item ?? null);
      setLimits(limitsResponse.items ?? []);
      setTransactions(transactionsResponse.items ?? []);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setIsForbidden(true);
        return;
      }
      setError(err instanceof Error ? err.message : t("fleet.errors.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [id, t, user?.token]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const handleToggleStatus = useCallback(async () => {
    if (!user?.token || !card) return;
    const action = card.status === "BLOCKED" ? unblockCard : blockCard;
    try {
      const response = await action(user.token, card.id);
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      if (response.item) {
        setCard(response.item);
        showToast({ kind: "success", text: t("fleet.cards.updated") });
      }
    } catch (err) {
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleet.errors.actionFailed") });
    }
  }, [card, showToast, t, user?.token]);

  const handleOpenLimit = () => {
    setLimitForm(defaultLimitState);
    setShowLimitModal(true);
  };

  const handleSetLimit = async () => {
    if (!user?.token || !id) return;
    try {
      const response = await setLimit(user.token, {
        scope_type: "card",
        scope_id: id,
        period: limitForm.period,
        amount_limit: limitForm.amount_limit ? Number(limitForm.amount_limit) : null,
        volume_limit_liters: limitForm.volume_limit_liters ? Number(limitForm.volume_limit_liters) : null,
        categories: limitForm.categories ? { values: limitForm.categories.split(",").map((item) => item.trim()) } : null,
        effective_from: limitForm.effective_from || null,
      });
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      if (response.item) {
        setLimits((prev) => [response.item!, ...prev]);
      }
      showToast({ kind: "success", text: t("fleet.limits.created") });
      setShowLimitModal(false);
    } catch (err) {
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleet.errors.actionFailed") });
    }
  };

  const limitColumns: Column<FleetLimit>[] = useMemo(
    () => [
      { key: "period", title: t("fleet.limits.period"), render: (row) => row.period ?? t("common.notAvailable") },
      { key: "amount", title: t("fleet.limits.amount"), render: (row) => (row.amount_limit ? formatMoney(row.amount_limit) : t("common.notAvailable")) },
      {
        key: "volume",
        title: t("fleet.limits.volume"),
        render: (row) => (row.volume_limit_liters ? formatLiters(row.volume_limit_liters) : t("common.notAvailable")),
      },
      {
        key: "effective",
        title: t("fleet.limits.effective"),
        render: (row) => (row.effective_from ? formatDateTime(row.effective_from) : t("common.notAvailable")),
      },
    ],
    [t],
  );

  const transactionColumns: Column<FleetTransaction>[] = useMemo(
    () => [
      { key: "occurred", title: t("fleet.spend.occurred"), render: (row) => (row.occurred_at ? formatDateTime(row.occurred_at) : t("common.notAvailable")) },
      { key: "amount", title: t("fleet.spend.amount"), render: (row) => (row.amount ? formatMoney(row.amount, row.currency ?? "RUB") : t("common.notAvailable")) },
      { key: "liters", title: t("fleet.spend.liters"), render: (row) => formatLiters(row.volume_liters) },
      { key: "merchant", title: t("fleet.spend.merchant"), render: (row) => row.merchant_name ?? t("common.notAvailable") },
      { key: "category", title: t("fleet.spend.category"), render: (row) => row.category ?? t("common.notAvailable") },
    ],
    [t],
  );

  if (loading) {
    return (
      <div className="page">
        <div className="page-header">
          <h1>{t("fleet.cards.detailsTitle")}</h1>
        </div>
        <div className="card state">{t("common.loading")}</div>
      </div>
    );
  }

  if (isForbidden) {
    return <AppForbiddenState message={t("fleet.errors.noPermission")} />;
  }

  if (unavailable) {
    return <FleetUnavailableState />;
  }

  if (!card) {
    return <div className="card state">{t("fleet.cards.notFound")}</div>;
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <button className="ghost" onClick={() => navigate(-1)} type="button">
            {t("common.back")}
          </button>
          <h1>{t("fleet.cards.detailsTitle")}</h1>
        </div>
        <div className="actions">
          {canManage ? (
            <button type="button" className="secondary" onClick={() => void handleToggleStatus()}>
              {card.status === "BLOCKED" ? t("fleet.cards.unblock") : t("fleet.cards.block")}
            </button>
          ) : null}
          <Link className="secondary" to={`/fleet/spend?card_id=${encodeURIComponent(card.id)}`}>
            {t("fleet.cards.openSpend")}
          </Link>
        </div>
      </div>
      {error ? <div className="card state">{error}</div> : null}
      <div className="card">
        <div className="card-header">
          <h2>{card.card_alias ?? t("common.notAvailable")}</h2>
          <StatusBadge status={card.status} />
        </div>
        <div className="card-grid">
          <div>
            <div className="muted">{t("fleet.cards.maskedPan")}</div>
            <div>{card.masked_pan ?? t("common.notAvailable")}</div>
          </div>
          <div>
            <div className="muted">{t("fleet.cards.currency")}</div>
            <div>{card.currency ?? t("common.notAvailable")}</div>
          </div>
          <div>
            <div className="muted">{t("fleet.cards.issued")}</div>
            <div>{card.issued_at ? formatDateTime(card.issued_at) : t("common.notAvailable")}</div>
          </div>
        </div>
      </div>

      <section className="section">
        <div className="section-header">
          <h2>{t("fleet.limits.title")}</h2>
          {canManageLimits ? (
            <button type="button" className="primary" onClick={handleOpenLimit}>
              {t("fleet.limits.set")}
            </button>
          ) : null}
        </div>
        <Table
          columns={limitColumns}
          data={limits.filter((limit) => limit.active !== false)}
          emptyState={{ title: t("fleet.limits.emptyTitle"), description: t("fleet.limits.emptyDescription") }}
        />
      </section>

      <section className="section">
        <div className="section-header">
          <h2>{t("fleet.spend.recent")}</h2>
        </div>
        <Table
          columns={transactionColumns}
          data={transactions}
          emptyState={{ title: t("fleet.spend.emptyTitle"), description: t("fleet.spend.emptyDescription") }}
        />
      </section>

      {showLimitModal ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-card">
            <h2>{t("fleet.limits.set")}</h2>
            <div className="form-grid">
              <label className="form-field">
                <span>{t("fleet.limits.period")}</span>
                <select
                  value={limitForm.period}
                  onChange={(event) => setLimitForm((prev) => ({ ...prev, period: event.target.value }))}
                >
                  <option value="daily">{t("fleet.limits.periodDaily")}</option>
                  <option value="weekly">{t("fleet.limits.periodWeekly")}</option>
                  <option value="monthly">{t("fleet.limits.periodMonthly")}</option>
                </select>
              </label>
              <label className="form-field">
                <span>{t("fleet.limits.amount")}</span>
                <input
                  type="number"
                  value={limitForm.amount_limit}
                  onChange={(event) => setLimitForm((prev) => ({ ...prev, amount_limit: event.target.value }))}
                />
              </label>
              <label className="form-field">
                <span>{t("fleet.limits.volume")}</span>
                <input
                  type="number"
                  value={limitForm.volume_limit_liters}
                  onChange={(event) => setLimitForm((prev) => ({ ...prev, volume_limit_liters: event.target.value }))}
                />
              </label>
              <label className="form-field">
                <span>{t("fleet.limits.categories")}</span>
                <input
                  value={limitForm.categories}
                  onChange={(event) => setLimitForm((prev) => ({ ...prev, categories: event.target.value }))}
                  placeholder={t("fleet.limits.categoriesPlaceholder")}
                />
              </label>
              <label className="form-field">
                <span>{t("fleet.limits.effective")}</span>
                <input
                  type="datetime-local"
                  value={limitForm.effective_from}
                  onChange={(event) => setLimitForm((prev) => ({ ...prev, effective_from: event.target.value }))}
                />
              </label>
            </div>
            <div className="actions">
              <button type="button" className="ghost" onClick={() => setShowLimitModal(false)}>
                {t("actions.comeBackLater")}
              </button>
              <button type="button" className="primary" onClick={() => void handleSetLimit()}>
                {t("fleet.limits.submit")}
              </button>
            </div>
          </div>
        </div>
      ) : null}
      <Toast toast={toast} />
    </div>
  );
}
