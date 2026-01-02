import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import { Table } from "../components/common/Table";
import type { Column } from "../components/common/Table";
import { AppForbiddenState } from "../components/states";
import { FleetUnavailableState } from "../components/FleetUnavailableState";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";
import type { FleetCard, FleetGroup, FleetTransaction } from "../types/fleet";
import { downloadTransactionsExport, exportTransactions, getSpendSummary, listCards, listGroups, listTransactions } from "../api/fleet";
import { ApiError } from "../api/http";
import { formatDateTime, formatLiters, formatMoney } from "../utils/format";

const toDateInput = (date: Date) => date.toISOString().slice(0, 10);

export function FleetSpendPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const { toast, showToast } = useToast();
  const [searchParams] = useSearchParams();
  const [groups, setGroups] = useState<FleetGroup[]>([]);
  const [cards, setCards] = useState<FleetCard[]>([]);
  const [transactions, setTransactions] = useState<FleetTransaction[]>([]);
  const [summary, setSummary] = useState({ totalAmount: 0, totalLiters: 0, avgPerDay: 0, topCategory: "" });
  const [linkExpires, setLinkExpires] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isForbidden, setIsForbidden] = useState(false);
  const [unavailable, setUnavailable] = useState(false);

  const defaultTo = toDateInput(new Date());
  const defaultFrom = toDateInput(new Date(Date.now() - 29 * 24 * 60 * 60 * 1000));

  const [from, setFrom] = useState(searchParams.get("from") ?? defaultFrom);
  const [to, setTo] = useState(searchParams.get("to") ?? defaultTo);
  const [groupId, setGroupId] = useState(searchParams.get("group_id") ?? "");
  const [cardId, setCardId] = useState(searchParams.get("card_id") ?? "");
  const [category, setCategory] = useState("");
  const [merchant, setMerchant] = useState("");

  const loadFilters = useCallback(async () => {
    if (!user?.token) return;
    try {
      const [groupsResponse, cardsResponse] = await Promise.all([
        listGroups(user.token),
        listCards(user.token),
      ]);
      if (groupsResponse.unavailable || cardsResponse.unavailable) {
        setUnavailable(true);
        return;
      }
      setGroups(groupsResponse.items ?? []);
      setCards(cardsResponse.items ?? []);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setIsForbidden(true);
        return;
      }
      setError(err instanceof Error ? err.message : t("fleet.errors.loadFailed"));
    }
  }, [t, user?.token]);

  const loadTransactions = useCallback(async () => {
    if (!user?.token) return;
    setLoading(true);
    setError(null);
    setIsForbidden(false);
    setUnavailable(false);
    try {
      const [transactionsResponse, summaryResponse] = await Promise.all([
        listTransactions(user.token, {
          from,
          to,
          card_id: cardId || undefined,
          group_id: groupId || undefined,
          category: category || undefined,
          merchant: merchant || undefined,
        }),
        getSpendSummary(user.token, {
          from,
          to,
          group_by: "category",
          card_id: cardId || undefined,
          group_id: groupId || undefined,
        }),
      ]);
      if (transactionsResponse.unavailable || summaryResponse.unavailable) {
        setUnavailable(true);
        return;
      }
      setTransactions(transactionsResponse.items ?? []);
      const totalAmount = (transactionsResponse.items ?? []).reduce((acc, item) => acc + Number(item.amount ?? 0), 0);
      const totalLiters = (transactionsResponse.items ?? []).reduce((acc, item) => acc + Number(item.volume_liters ?? 0), 0);
      const days = Math.max(1, Math.ceil((new Date(to).getTime() - new Date(from).getTime()) / (1000 * 60 * 60 * 24)) + 1);
      const avgPerDay = totalAmount / days;
      const topCategoryRow = (summaryResponse.rows ?? []).sort((a, b) => Number(b.amount) - Number(a.amount))[0];
      setSummary({ totalAmount, totalLiters, avgPerDay, topCategory: topCategoryRow?.key ?? "" });
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setIsForbidden(true);
        return;
      }
      setError(err instanceof Error ? err.message : t("fleet.errors.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [cardId, category, from, groupId, merchant, t, to, user?.token]);

  useEffect(() => {
    void loadFilters();
  }, [loadFilters]);

  useEffect(() => {
    void loadTransactions();
  }, [loadTransactions]);

  const handleExport = async () => {
    if (!user?.token) return;
    try {
      const response = await exportTransactions(user.token, {
        from,
        to,
        card_id: cardId || undefined,
        group_id: groupId || undefined,
        format: "csv",
      });
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      let url = response.item?.url;
      if (!url && response.item?.export_id) {
        const download = await downloadTransactionsExport(user.token, response.item.export_id);
        if (download.unavailable) {
          setUnavailable(true);
          return;
        }
        url = download.item?.url ?? undefined;
        if (download.item?.expires_in) {
          setLinkExpires(download.item.expires_in);
        }
      }
      if (url) {
        window.open(url, "_blank", "noopener");
        if (response.item?.expires_in) {
          setLinkExpires(response.item.expires_in);
        }
        showToast({ kind: "success", text: t("fleet.spend.exportReady") });
      } else {
        showToast({ kind: "error", text: t("fleet.spend.exportFailed") });
      }
    } catch (err) {
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleet.errors.actionFailed") });
    }
  };

  const columns: Column<FleetTransaction>[] = useMemo(
    () => [
      { key: "occurred", title: t("fleet.spend.occurred"), render: (row) => (row.occurred_at ? formatDateTime(row.occurred_at) : t("common.notAvailable")) },
      { key: "card", title: t("fleet.spend.card"), render: (row) => cards.find((card) => card.id === row.card_id)?.card_alias ?? t("common.notAvailable") },
      { key: "amount", title: t("fleet.spend.amount"), render: (row) => (row.amount ? formatMoney(row.amount, row.currency ?? "RUB") : t("common.notAvailable")) },
      { key: "liters", title: t("fleet.spend.liters"), render: (row) => formatLiters(row.volume_liters) },
      { key: "merchant", title: t("fleet.spend.merchant"), render: (row) => row.merchant_name ?? t("common.notAvailable") },
      { key: "category", title: t("fleet.spend.category"), render: (row) => row.category ?? t("common.notAvailable") },
    ],
    [cards, t],
  );

  if (loading) {
    return (
      <div className="page">
        <div className="page-header">
          <h1>{t("fleet.spend.title")}</h1>
        </div>
        <Table columns={columns} data={[]} loading />
      </div>
    );
  }

  if (isForbidden) {
    return <AppForbiddenState message={t("fleet.errors.noPermissionGroup")} />;
  }

  if (unavailable) {
    return <FleetUnavailableState />;
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>{t("fleet.spend.title")}</h1>
        <div className="actions">
          <button type="button" className="secondary" onClick={() => void loadTransactions()}>
            {t("actions.refresh")}
          </button>
          <button type="button" className="primary" onClick={() => void handleExport()}>
            {t("fleet.spend.exportCsv")}
          </button>
        </div>
      </div>
      <div className="filters">
        <div className="filter">
          <span className="label">{t("fleet.spend.from")}</span>
          <input type="date" value={from} onChange={(event) => setFrom(event.target.value)} />
        </div>
        <div className="filter">
          <span className="label">{t("fleet.spend.to")}</span>
          <input type="date" value={to} onChange={(event) => setTo(event.target.value)} />
        </div>
        <div className="filter">
          <span className="label">{t("fleet.spend.group")}</span>
          <select value={groupId} onChange={(event) => setGroupId(event.target.value)}>
            <option value="">{t("fleet.spend.groupAll")}</option>
            {groups.map((group) => (
              <option key={group.id} value={group.id}>
                {group.name}
              </option>
            ))}
          </select>
        </div>
        <div className="filter">
          <span className="label">{t("fleet.spend.card")}</span>
          <select value={cardId} onChange={(event) => setCardId(event.target.value)}>
            <option value="">{t("fleet.spend.cardAll")}</option>
            {cards.map((card) => (
              <option key={card.id} value={card.id}>
                {card.card_alias ?? card.masked_pan ?? t("fleet.cards.aliasFallback")}
              </option>
            ))}
          </select>
        </div>
        <div className="filter">
          <span className="label">{t("fleet.spend.category")}</span>
          <input value={category} onChange={(event) => setCategory(event.target.value)} placeholder={t("fleet.spend.categoryPlaceholder")} />
        </div>
        <div className="filter">
          <span className="label">{t("fleet.spend.merchant")}</span>
          <input value={merchant} onChange={(event) => setMerchant(event.target.value)} placeholder={t("fleet.spend.merchantPlaceholder")} />
        </div>
      </div>
      {error ? <div className="card state">{error}</div> : null}
      <div className="card-grid">
        <div className="card">
          <div className="muted">{t("fleet.spend.totalAmount")}</div>
          <div>{formatMoney(summary.totalAmount)}</div>
        </div>
        <div className="card">
          <div className="muted">{t("fleet.spend.totalLiters")}</div>
          <div>{formatLiters(summary.totalLiters)}</div>
        </div>
        <div className="card">
          <div className="muted">{t("fleet.spend.avgPerDay")}</div>
          <div>{formatMoney(summary.avgPerDay)}</div>
        </div>
        <div className="card">
          <div className="muted">{t("fleet.spend.topCategory")}</div>
          <div>{summary.topCategory || t("fleet.spend.noCategory")}</div>
        </div>
      </div>
      {linkExpires ? <div className="muted">{t("fleet.spend.linkExpires", { seconds: linkExpires })}</div> : null}
      <Table
        columns={columns}
        data={transactions.filter((tx) => {
          const categoryMatch = category ? (tx.category ?? "").toLowerCase().includes(category.toLowerCase()) : true;
          const merchantMatch = merchant ? (tx.merchant_name ?? "").toLowerCase().includes(merchant.toLowerCase()) : true;
          return categoryMatch && merchantMatch;
        })}
        emptyState={{ title: t("fleet.spend.emptyTitle"), description: t("fleet.spend.emptyDescription") }}
      />
      <Toast toast={toast} />
    </div>
  );
}
