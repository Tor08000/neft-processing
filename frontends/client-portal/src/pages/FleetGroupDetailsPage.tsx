import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import { AppForbiddenState } from "../components/states";
import { FleetUnavailableState } from "../components/FleetUnavailableState";
import { Table } from "../components/common/Table";
import type { Column } from "../components/common/Table";
import { RoleBadge } from "../components/RoleBadge";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";
import type { FleetAccess, FleetCard, FleetEmployee, FleetGroup, FleetLimit } from "../types/fleet";
import {
  addCardToGroup,
  getGroup,
  grantGroupAccess,
  listCards,
  listEmployees,
  listGroupAccess,
  listLimits,
  removeCardFromGroup,
  revokeGroupAccess,
  revokeLimit,
  setLimit,
  getSpendSummary,
  exportTransactions,
  downloadTransactionsExport,
} from "../api/fleet";
import { ApiError } from "../api/http";
import { formatDateTime, formatMoney } from "../utils/format";
import {
  canManageFleetGroups,
  canManageFleetLimits,
  deriveGroupRole,
  isGroupRoleAtLeast,
} from "../utils/fleetPermissions";

const tabKeys = ["cards", "access", "limits", "spend"] as const;

type TabKey = (typeof tabKeys)[number];

const defaultLimitForm = {
  period: "daily",
  amount_limit: "",
  volume_limit_liters: "",
};

export function FleetGroupDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const { toast, showToast } = useToast();
  const [group, setGroup] = useState<FleetGroup | null>(null);
  const [groupCards, setGroupCards] = useState<FleetCard[]>([]);
  const [cards, setCards] = useState<FleetCard[]>([]);
  const [employees, setEmployees] = useState<FleetEmployee[]>([]);
  const [accessList, setAccessList] = useState<FleetAccess[]>([]);
  const [limits, setLimits] = useState<FleetLimit[]>([]);
  const [activeTab, setActiveTab] = useState<TabKey>("cards");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isForbidden, setIsForbidden] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [selectedCardId, setSelectedCardId] = useState("");
  const [selectedEmployeeId, setSelectedEmployeeId] = useState("");
  const [selectedRole, setSelectedRole] = useState("viewer");
  const [showLimitModal, setShowLimitModal] = useState(false);
  const [limitForm, setLimitForm] = useState(defaultLimitForm);
  const [summaryAmount, setSummaryAmount] = useState<string | null>(null);
  const [summaryExpires, setSummaryExpires] = useState<number | null>(null);

  const canManage = canManageFleetGroups(user);
  const canManageLimits = canManageFleetLimits(user);

  const loadGroup = useCallback(async () => {
    if (!user?.token || !id) return;
    setLoading(true);
    setError(null);
    setIsForbidden(false);
    setUnavailable(false);
    try {
      const [groupResponse, cardsResponse] = await Promise.all([getGroup(user.token, id), listCards(user.token)]);
      if (groupResponse.unavailable || cardsResponse.unavailable) {
        setUnavailable(true);
        return;
      }
      setGroup(groupResponse.item ?? null);
      setCards(cardsResponse.items ?? []);
      setGroupCards(groupResponse.item?.cards ?? []);
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

  const loadAccess = useCallback(async () => {
    if (!user?.token || !id) return;
    try {
      const [accessResponse, employeesResponse] = await Promise.all([
        listGroupAccess(user.token, id),
        listEmployees(user.token),
      ]);
      if (accessResponse.unavailable || employeesResponse.unavailable) {
        setUnavailable(true);
        return;
      }
      setAccessList(accessResponse.items ?? []);
      setEmployees(employeesResponse.items ?? []);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setIsForbidden(true);
        return;
      }
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleet.errors.loadFailed") });
    }
  }, [id, showToast, t, user?.token]);

  const loadLimits = useCallback(async () => {
    if (!user?.token || !id) return;
    try {
      const response = await listLimits(user.token, { scope_type: "group", scope_id: id });
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      setLimits(response.items ?? []);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setIsForbidden(true);
        return;
      }
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleet.errors.loadFailed") });
    }
  }, [id, showToast, t, user?.token]);

  const loadSpendSummary = useCallback(async () => {
    if (!user?.token || !id) return;
    try {
      const response = await getSpendSummary(user.token, { group_by: "category", group_id: id });
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      const topRow = response.rows?.[0];
      setSummaryAmount(topRow ? formatMoney(topRow.amount) : null);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setIsForbidden(true);
        return;
      }
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleet.errors.loadFailed") });
    }
  }, [id, showToast, t, user?.token]);

  useEffect(() => {
    void loadGroup();
  }, [loadGroup]);

  useEffect(() => {
    if (activeTab === "access") {
      void loadAccess();
    }
    if (activeTab === "limits") {
      void loadLimits();
    }
    if (activeTab === "spend") {
      void loadSpendSummary();
    }
  }, [activeTab, loadAccess, loadLimits, loadSpendSummary]);

  const myRole = deriveGroupRole(user, group?.my_role);
  const canAdmin = isGroupRoleAtLeast(myRole, "admin");
  const canManager = isGroupRoleAtLeast(myRole, "manager");

  const handleAddCard = async () => {
    if (!user?.token || !id || !selectedCardId) return;
    try {
      const response = await addCardToGroup(user.token, id, selectedCardId);
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      const card = cards.find((item) => item.id === selectedCardId);
      if (card) {
        setGroupCards((prev) => [...prev, card]);
      }
      setSelectedCardId("");
      showToast({ kind: "success", text: t("fleet.groups.cardAdded") });
    } catch (err) {
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleet.errors.actionFailed") });
    }
  };

  const handleRemoveCard = async (cardId: string) => {
    if (!user?.token || !id) return;
    try {
      const response = await removeCardFromGroup(user.token, id, cardId);
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      setGroupCards((prev) => prev.filter((item) => item.id !== cardId));
      showToast({ kind: "success", text: t("fleet.groups.cardRemoved") });
    } catch (err) {
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleet.errors.actionFailed") });
    }
  };

  const handleGrantAccess = async () => {
    if (!user?.token || !id || !selectedEmployeeId) return;
    try {
      const response = await grantGroupAccess(user.token, id, { employee_id: selectedEmployeeId, role: selectedRole });
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      if (response.item) {
        setAccessList((prev) => [response.item!, ...prev]);
      }
      setSelectedEmployeeId("");
      showToast({ kind: "success", text: t("fleet.groups.accessGranted") });
    } catch (err) {
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleet.errors.actionFailed") });
    }
  };

  const handleRevokeAccess = async (employeeId: string) => {
    if (!user?.token || !id) return;
    try {
      const response = await revokeGroupAccess(user.token, id, { employee_id: employeeId });
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      if (response.item) {
        setAccessList((prev) => prev.filter((item) => item.employee_id !== employeeId));
      }
      showToast({ kind: "success", text: t("fleet.groups.accessRevoked") });
    } catch (err) {
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleet.errors.actionFailed") });
    }
  };

  const handleSetLimit = async () => {
    if (!user?.token || !id) return;
    try {
      const response = await setLimit(user.token, {
        scope_type: "group",
        scope_id: id,
        period: limitForm.period,
        amount_limit: limitForm.amount_limit ? Number(limitForm.amount_limit) : null,
        volume_limit_liters: limitForm.volume_limit_liters ? Number(limitForm.volume_limit_liters) : null,
      });
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      if (response.item) {
        setLimits((prev) => [response.item!, ...prev]);
      }
      setShowLimitModal(false);
      showToast({ kind: "success", text: t("fleet.limits.created") });
    } catch (err) {
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleet.errors.actionFailed") });
    }
  };

  const handleRevokeLimit = async (limitId: string) => {
    if (!user?.token) return;
    try {
      const response = await revokeLimit(user.token, { limit_id: limitId });
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      setLimits((prev) => prev.filter((item) => item.id !== limitId));
      showToast({ kind: "success", text: t("fleet.limits.revoked") });
    } catch (err) {
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleet.errors.actionFailed") });
    }
  };

  const handleExport = async () => {
    if (!user?.token || !id) return;
    try {
      const response = await exportTransactions(user.token, { group_id: id, format: "csv" });
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
          setSummaryExpires(download.item.expires_in);
        }
      }
      if (url) {
        window.open(url, "_blank", "noopener");
        if (response.item?.expires_in) {
          setSummaryExpires(response.item.expires_in);
        }
        showToast({ kind: "success", text: t("fleet.spend.exportReady") });
      } else {
        showToast({ kind: "error", text: t("fleet.spend.exportFailed") });
      }
    } catch (err) {
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleet.errors.actionFailed") });
    }
  };

  const employeeMap = useMemo(() => {
    return employees.reduce<Record<string, FleetEmployee>>((acc, item) => {
      acc[item.id] = item;
      return acc;
    }, {});
  }, [employees]);

  const cardColumns: Column<FleetCard>[] = [
    { key: "alias", title: t("fleet.cards.alias"), render: (row) => row.card_alias ?? t("common.notAvailable") },
    { key: "masked", title: t("fleet.cards.maskedPan"), render: (row) => row.masked_pan ?? t("common.notAvailable") },
    {
      key: "actions",
      title: t("fleet.groups.actions"),
      render: (row) =>
        canAdmin ? (
          <button type="button" className="ghost" onClick={() => void handleRemoveCard(row.id)}>
            {t("fleet.groups.removeCard")}
          </button>
        ) : (
          <span className="muted">{t("fleet.groups.removeRestricted")}</span>
        ),
    },
  ];

  const accessColumns: Column<FleetAccess>[] = [
    {
      key: "employee",
      title: t("fleet.employees.email"),
      render: (row) => employeeMap[row.employee_id]?.email ?? t("common.notAvailable"),
    },
    { key: "role", title: t("fleet.groups.role"), render: (row) => <RoleBadge role={row.role} /> },
    {
      key: "actions",
      title: t("fleet.groups.actions"),
      render: (row) =>
        canAdmin ? (
          <button type="button" className="ghost" onClick={() => void handleRevokeAccess(row.employee_id)}>
            {t("fleet.groups.revoke")}
          </button>
        ) : (
          <span className="muted">{t("fleet.groups.revokeRestricted")}</span>
        ),
    },
  ];

  const limitColumns: Column<FleetLimit>[] = [
    { key: "period", title: t("fleet.limits.period"), render: (row) => row.period ?? t("common.notAvailable") },
    { key: "amount", title: t("fleet.limits.amount"), render: (row) => (row.amount_limit ? formatMoney(row.amount_limit) : t("common.notAvailable")) },
    {
      key: "actions",
      title: t("fleet.groups.actions"),
      render: (row) =>
        canManager ? (
          <button type="button" className="ghost" onClick={() => void handleRevokeLimit(row.id)}>
            {t("fleet.limits.revoke")}
          </button>
        ) : (
          <span className="muted">{t("fleet.limits.revokeRestricted")}</span>
        ),
    },
  ];

  const tabs = [
    { key: "cards", label: t("fleet.groups.tabs.cards") },
    { key: "access", label: t("fleet.groups.tabs.access") },
    { key: "limits", label: t("fleet.groups.tabs.limits") },
    { key: "spend", label: t("fleet.groups.tabs.spend") },
  ] as const;

  if (loading) {
    return (
      <div className="page">
        <div className="page-header">
          <h1>{t("fleet.groups.detailsTitle")}</h1>
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

  if (!group) {
    return <div className="card state">{t("fleet.groups.notFound")}</div>;
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <button className="ghost" onClick={() => navigate(-1)} type="button">
            {t("common.back")}
          </button>
          <h1>{t("fleet.groups.detailsTitle")}</h1>
        </div>
        <div className="actions">
          <RoleBadge role={myRole} />
          <Link className="secondary" to={`/fleet/spend?group_id=${encodeURIComponent(group.id)}`}>
            {t("fleet.groups.viewSpend")}
          </Link>
        </div>
      </div>
      {error ? <div className="card state">{error}</div> : null}
      <div className="card">
        <div className="card-header">
          <h2>{group.name}</h2>
          <span className="muted">{group.description ?? t("fleet.groups.noDescription")}</span>
        </div>
      </div>

      <div className="tabs">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            className={activeTab === tab.key ? "primary" : "secondary"}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "cards" ? (
        <section className="section">
          <div className="section-header">
            <h2>{t("fleet.groups.cardsTitle")}</h2>
            {canAdmin && canManage ? (
              <div className="actions">
                <select value={selectedCardId} onChange={(event) => setSelectedCardId(event.target.value)}>
                  <option value="">{t("fleet.groups.selectCard")}</option>
                  {cards.map((card) => (
                    <option key={card.id} value={card.id}>
                      {card.card_alias ?? card.masked_pan ?? t("fleet.cards.aliasFallback")}
                    </option>
                  ))}
                </select>
                <button type="button" className="primary" onClick={() => void handleAddCard()} disabled={!selectedCardId}>
                  {t("fleet.groups.addCard")}
                </button>
              </div>
            ) : null}
          </div>
          <Table
            columns={cardColumns}
            data={groupCards}
            emptyState={{ title: t("fleet.groups.cardsEmpty"), description: t("fleet.groups.cardsEmptyDescription") }}
          />
        </section>
      ) : null}

      {activeTab === "access" ? (
        <section className="section">
          <div className="section-header">
            <h2>{t("fleet.groups.accessTitle")}</h2>
            {canAdmin ? (
              <div className="actions">
                <select value={selectedEmployeeId} onChange={(event) => setSelectedEmployeeId(event.target.value)}>
                  <option value="">{t("fleet.groups.selectEmployee")}</option>
                  {employees.map((employee) => (
                    <option key={employee.id} value={employee.id}>
                      {employee.email}
                    </option>
                  ))}
                </select>
                <select value={selectedRole} onChange={(event) => setSelectedRole(event.target.value)}>
                  <option value="viewer">{t("fleet.roles.viewer")}</option>
                  <option value="manager">{t("fleet.roles.manager")}</option>
                  <option value="admin">{t("fleet.roles.admin")}</option>
                </select>
                <button type="button" className="primary" onClick={() => void handleGrantAccess()} disabled={!selectedEmployeeId}>
                  {t("fleet.groups.grant")}
                </button>
              </div>
            ) : null}
          </div>
          <Table
            columns={accessColumns}
            data={accessList}
            emptyState={{ title: t("fleet.groups.accessEmpty"), description: t("fleet.groups.accessEmptyDescription") }}
          />
        </section>
      ) : null}

      {activeTab === "limits" ? (
        <section className="section">
          <div className="section-header">
            <h2>{t("fleet.limits.title")}</h2>
            {canManager && canManageLimits ? (
              <button type="button" className="primary" onClick={() => setShowLimitModal(true)}>
                {t("fleet.limits.set")}
              </button>
            ) : null}
          </div>
          <Table
            columns={limitColumns}
            data={limits}
            emptyState={{ title: t("fleet.limits.emptyTitle"), description: t("fleet.limits.emptyDescription") }}
          />
        </section>
      ) : null}

      {activeTab === "spend" ? (
        <section className="section">
          <div className="section-header">
            <h2>{t("fleet.groups.spendTitle")}</h2>
            <button type="button" className="secondary" onClick={() => void handleExport()}>
              {t("fleet.spend.exportCsv")}
            </button>
          </div>
          <div className="card">
            <div className="muted">{t("fleet.spend.topCategory")}</div>
            <div>{summaryAmount ?? t("fleet.spend.noSummary")}</div>
            {summaryExpires ? <div className="muted small">{t("fleet.spend.linkExpires", { seconds: summaryExpires })}</div> : null}
            <div className="actions">
              <Link className="ghost" to={`/fleet/spend?group_id=${encodeURIComponent(group.id)}`}>
                {t("fleet.groups.viewTransactions")}
              </Link>
            </div>
          </div>
        </section>
      ) : null}

      {showLimitModal ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-card">
            <h2>{t("fleet.limits.set")}</h2>
            <div className="form-grid">
              <label className="form-field">
                <span>{t("fleet.limits.period")}</span>
                <select value={limitForm.period} onChange={(event) => setLimitForm((prev) => ({ ...prev, period: event.target.value }))}>
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
