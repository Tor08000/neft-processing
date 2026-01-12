import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import { Table } from "../components/common/Table";
import type { Column } from "../components/common/Table";
import { ConfirmActionModal } from "../components/ConfirmActionModal";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";
import { AppErrorState, AppForbiddenState } from "../components/states";
import { FleetUnavailableState } from "../components/FleetUnavailableState";
import { ApiError } from "../api/http";
import { listCards, listGroups } from "../api/fleet";
import { createPolicy, disablePolicy, listPolicies } from "../api/fleetPolicies";
import type { FleetCard, FleetGroup } from "../types/fleet";
import type { FleetPolicy } from "../types/fleetPolicies";
import { CopyButton } from "../components/CopyButton";
import { formatDateTime } from "../utils/format";
import { hasAnyRole } from "../utils/roles";
import { isGroupRoleAtLeast, normalizeGroupRole } from "../utils/fleetPermissions";
import type { FleetPolicyRole } from "../utils/fleetPolicyPermissions";
import { canManagePolicies } from "../utils/fleetPolicyPermissions";
import { PolicyCenterTabs } from "../components/PolicyCenterTabs";
import { PolicyCenterRulesTabs } from "../components/PolicyCenterRulesTabs";

const getPolicyRole = (user: ReturnType<typeof useAuth>["user"], groups: FleetGroup[]): FleetPolicyRole => {
  if (hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_FLEET_MANAGER"])) return "admin";
  const hasManagerGroup = groups.some((group) => isGroupRoleAtLeast(normalizeGroupRole(group.my_role), "manager"));
  return hasManagerGroup ? "manager" : "viewer";
};

const getScopeBadgeClass = (scopeType?: string | null) => {
  if (scopeType === "CLIENT") return "neft-chip neft-chip-info";
  if (scopeType === "GROUP") return "neft-chip neft-chip-warn";
  if (scopeType === "CARD") return "neft-chip neft-chip-muted";
  return "neft-chip neft-chip-muted";
};

const getStatusBadgeClass = (status?: string | null) =>
  status === "DISABLED" ? "neft-chip neft-chip-muted" : "neft-chip neft-chip-ok";

const getActionBadgeClass = (action?: string | null) => {
  if (action === "AUTO_BLOCK_CARD") return "neft-chip neft-chip-warn";
  if (action === "ESCALATE_CASE") return "neft-chip neft-chip-info";
  return "neft-chip neft-chip-muted";
};

export function FleetPoliciesPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const { toast, showToast } = useToast();
  const [policies, setPolicies] = useState<FleetPolicy[]>([]);
  const [groups, setGroups] = useState<FleetGroup[]>([]);
  const [cards, setCards] = useState<FleetCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isForbidden, setIsForbidden] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [scopeFilter, setScopeFilter] = useState("");
  const [triggerFilter, setTriggerFilter] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [activeOnly, setActiveOnly] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [scopeType, setScopeType] = useState("CLIENT");
  const [scopeId, setScopeId] = useState("");
  const [triggerType, setTriggerType] = useState("");
  const [severityMin, setSeverityMin] = useState("");
  const [breachKind, setBreachKind] = useState("");
  const [action, setAction] = useState("");
  const [cooldown, setCooldown] = useState("300");
  const [formError, setFormError] = useState<string | null>(null);
  const [disableTarget, setDisableTarget] = useState<FleetPolicy | null>(null);

  const loadPolicies = useCallback(async () => {
    if (!user?.token) return;
    setLoading(true);
    setError(null);
    setIsForbidden(false);
    setUnavailable(false);
    try {
      const [policiesResponse, groupsResponse, cardsResponse] = await Promise.all([
        listPolicies(user.token),
        listGroups(user.token),
        listCards(user.token),
      ]);
      if (policiesResponse.unavailable || groupsResponse.unavailable || cardsResponse.unavailable) {
        setUnavailable(true);
        return;
      }
      setPolicies(policiesResponse.items);
      setGroups(groupsResponse.items);
      setCards(cardsResponse.items);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setIsForbidden(true);
        return;
      }
      setError(err instanceof Error ? err.message : t("fleetPolicies.errors.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [t, user?.token]);

  useEffect(() => {
    void loadPolicies();
  }, [loadPolicies]);

  const policyRole = useMemo(() => getPolicyRole(user, groups), [groups, user]);
  const manageableGroups = useMemo(
    () => groups.filter((group) => isGroupRoleAtLeast(normalizeGroupRole(group.my_role), "manager")),
    [groups],
  );
  const canCreateAny = policyRole === "admin" || manageableGroups.length > 0;

  useEffect(() => {
    if (policyRole === "manager") {
      setScopeType("GROUP");
    }
  }, [policyRole]);

  const resetForm = () => {
    setScopeType(policyRole === "manager" ? "GROUP" : "CLIENT");
    setScopeId("");
    setTriggerType("");
    setSeverityMin("");
    setBreachKind("");
    setAction("");
    setCooldown("300");
    setFormError(null);
  };

  const resolveScopeName = (policy: FleetPolicy) => {
    if (policy.scope_type === "CLIENT") return t("fleetPolicies.scopeClient");
    if (policy.scope_type === "GROUP") {
      if (policy.group_name) return policy.group_name;
      const match = groups.find((group) => group.id === policy.scope_id);
      return match?.name ?? t("fleetPolicies.scopeGroupFallback");
    }
    if (policy.scope_type === "CARD") {
      if (policy.card_alias) return policy.card_alias;
      const match = cards.find((card) => card.id === policy.scope_id);
      return match?.card_alias ?? t("fleetPolicies.scopeCardFallback");
    }
    return t("common.notAvailable");
  };

  const filteredPolicies = useMemo(() => {
    return policies.filter((policy) => {
      const scopeOk = scopeFilter ? policy.scope_type === scopeFilter : true;
      const triggerOk = triggerFilter ? policy.trigger_type === triggerFilter : true;
      const actionOk = actionFilter ? policy.action === actionFilter : true;
      const status = policy.status ?? "ACTIVE";
      const activeOk = activeOnly ? status !== "DISABLED" : true;
      return scopeOk && triggerOk && actionOk && activeOk;
    });
  }, [actionFilter, activeOnly, policies, scopeFilter, triggerFilter]);

  const handleCreate = async () => {
    if (!user?.token) return;
    if (!triggerType || !severityMin || !action) {
      setFormError(t("fleetPolicies.validationRequired"));
      return;
    }
    if ((scopeType === "GROUP" || scopeType === "CARD") && !scopeId) {
      setFormError(t("fleetPolicies.validationScope"));
      return;
    }
    if (triggerType === "LIMIT_BREACH" && !breachKind) {
      setFormError(t("fleetPolicies.validationBreachKind"));
      return;
    }
    const cooldownValue = Number(cooldown);
    if (!Number.isFinite(cooldownValue) || cooldownValue <= 0) {
      setFormError(t("fleetPolicies.validationCooldown"));
      return;
    }
    setFormError(null);
    try {
      const response = await createPolicy(user.token, {
        scope_type: scopeType,
        scope_id: scopeType === "CLIENT" ? undefined : scopeId,
        trigger_type: triggerType,
        severity_min: severityMin,
        breach_kind: triggerType === "LIMIT_BREACH" ? breachKind : undefined,
        action,
        cooldown_seconds: cooldownValue,
      });
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      if (response.item) {
        setPolicies((prev) => [response.item!, ...prev]);
      }
      showToast({ kind: "success", text: t("fleetPolicies.created") });
      setShowCreateModal(false);
      resetForm();
    } catch (err) {
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleetPolicies.errors.actionFailed") });
    }
  };

  const handleDisable = async () => {
    if (!user?.token || !disableTarget) return;
    try {
      const response = await disablePolicy(user.token, disableTarget.id);
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      const updated = response.item ?? { ...disableTarget, status: "DISABLED" };
      setPolicies((prev) => prev.map((policy) => (policy.id === disableTarget.id ? { ...policy, ...updated } : policy)));
      showToast({ kind: "success", text: t("fleetPolicies.disabled") });
      setDisableTarget(null);
    } catch (err) {
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleetPolicies.errors.actionFailed") });
    }
  };

  const columns: Column<FleetPolicy>[] = useMemo(
    () => [
      {
        key: "scopeBadge",
        title: t("fleetPolicies.scope"),
        render: (policy) => (
          <span className={getScopeBadgeClass(policy.scope_type)}>
            {policy.scope_type === "CLIENT"
              ? t("fleetPolicies.scopeClient")
              : policy.scope_type === "GROUP"
                ? t("fleetPolicies.scopeGroup")
                : policy.scope_type === "CARD"
                  ? t("fleetPolicies.scopeCard")
                  : policy.scope_type ?? t("common.notAvailable")}
          </span>
        ),
      },
      {
        key: "scopeName",
        title: t("fleetPolicies.scopeName"),
        render: (policy) => resolveScopeName(policy),
      },
      {
        key: "trigger",
        title: t("fleetPolicies.trigger"),
        render: (policy) =>
          policy.trigger_type === "LIMIT_BREACH"
            ? t("fleetPolicies.triggerLimit")
            : policy.trigger_type === "ANOMALY"
              ? t("fleetPolicies.triggerAnomaly")
              : policy.trigger_type ?? t("common.notAvailable"),
      },
      {
        key: "severity",
        title: t("fleetPolicies.severityMin"),
        render: (policy) => <span className="neft-chip neft-chip-muted">{policy.severity_min ?? "—"}</span>,
      },
      {
        key: "breachKind",
        title: t("fleetPolicies.breachKind"),
        render: (policy) => {
          if (policy.trigger_type !== "LIMIT_BREACH") return "—";
          if (policy.breach_kind === "HARD") return t("fleetPolicies.breachKindHard");
          if (policy.breach_kind === "SOFT") return t("fleetPolicies.breachKindSoft");
          if (policy.breach_kind === "ANY") return t("fleetPolicies.breachKindAny");
          return policy.breach_kind ?? "—";
        },
      },
      {
        key: "action",
        title: t("fleetPolicies.action"),
        render: (policy) => (
          <span className={getActionBadgeClass(policy.action)}>
            {policy.action === "NOTIFY_ONLY"
              ? t("fleetPolicies.actionNotify")
              : policy.action === "AUTO_BLOCK_CARD"
                ? t("fleetPolicies.actionAutoBlock")
                : policy.action === "ESCALATE_CASE"
                  ? t("fleetPolicies.actionEscalate")
                  : policy.action ?? t("common.notAvailable")}
          </span>
        ),
      },
      {
        key: "cooldown",
        title: t("fleetPolicies.cooldown"),
        render: (policy) => t("fleetPolicies.cooldownValue", { value: policy.cooldown_seconds ?? 0 }),
      },
      {
        key: "status",
        title: t("fleetPolicies.status"),
        render: (policy) => (
          <span className={getStatusBadgeClass(policy.status)}>
            {policy.status === "DISABLED" ? t("fleetPolicies.statusDisabled") : t("fleetPolicies.statusActive")}
          </span>
        ),
      },
      {
        key: "createdAt",
        title: t("fleetPolicies.createdAt"),
        render: (policy) => (policy.created_at ? formatDateTime(policy.created_at) : "—"),
      },
      {
        key: "actions",
        title: t("fleetPolicies.actions"),
        render: (policy) => (
          <div className="actions">
            {canManagePolicies(policyRole, policy.scope_type ?? "") ? (
              <button
                type="button"
                className="ghost"
                onClick={() => setDisableTarget(policy)}
                disabled={policy.status === "DISABLED"}
              >
                {t("fleetPolicies.disable")}
              </button>
            ) : null}
            {policy.id ? (
              <details className="policy-advanced">
                <summary>{t("fleetPolicies.advanced")}</summary>
                <div className="policy-advanced__content">
                  <div className="muted small">{t("fleetPolicies.policyId")}</div>
                  <CopyButton value={policy.id} label={t("fleetPolicies.copyId")} />
                </div>
              </details>
            ) : null}
          </div>
        ),
      },
    ],
    [policyRole, resolveScopeName, t],
  );

  if (loading) {
    return (
      <div className="page">
        <div className="page-header">
          <h1>{t("policyCenter.actionsTitle")}</h1>
        </div>
        <PolicyCenterTabs />
        <PolicyCenterRulesTabs />
        <div className="card state">{t("common.loading")}</div>
      </div>
    );
  }

  if (unavailable) {
    return <FleetUnavailableState />;
  }

  if (isForbidden) {
    return <AppForbiddenState message={t("fleetPolicies.errors.noPermission")} />;
  }

  if (error) {
    return (
      <div className="page">
        <div className="page-header">
          <h1>{t("policyCenter.actionsTitle")}</h1>
        </div>
        <PolicyCenterTabs />
        <PolicyCenterRulesTabs />
        <AppErrorState message={error} onRetry={() => void loadPolicies()} />
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>{t("policyCenter.actionsTitle")}</h1>
        <div className="actions">
          <Link to="/fleet/policy-center/executions" className="secondary">
            {t("fleetPolicies.executionsLink")}
          </Link>
          {canCreateAny ? (
            <button
              type="button"
              className="primary"
              onClick={() => {
                resetForm();
                setShowCreateModal(true);
              }}
            >
              {t("fleetPolicies.create")}
            </button>
          ) : null}
          <button type="button" className="secondary" onClick={() => void loadPolicies()}>
            {t("actions.refresh")}
          </button>
        </div>
      </div>
      <PolicyCenterTabs />
      <PolicyCenterRulesTabs />
      <div className="card filters">
        <label className="filter">
          <span>{t("fleetPolicies.scope")}</span>
          <select value={scopeFilter} onChange={(event) => setScopeFilter(event.target.value)}>
            <option value="">{t("fleetPolicies.scopeAll")}</option>
            <option value="CLIENT">{t("fleetPolicies.scopeClient")}</option>
            <option value="GROUP">{t("fleetPolicies.scopeGroup")}</option>
            <option value="CARD">{t("fleetPolicies.scopeCard")}</option>
          </select>
        </label>
        <label className="filter">
          <span>{t("fleetPolicies.trigger")}</span>
          <select value={triggerFilter} onChange={(event) => setTriggerFilter(event.target.value)}>
            <option value="">{t("fleetPolicies.triggerAll")}</option>
            <option value="LIMIT_BREACH">{t("fleetPolicies.triggerLimit")}</option>
            <option value="ANOMALY">{t("fleetPolicies.triggerAnomaly")}</option>
          </select>
        </label>
        <label className="filter">
          <span>{t("fleetPolicies.action")}</span>
          <select value={actionFilter} onChange={(event) => setActionFilter(event.target.value)}>
            <option value="">{t("fleetPolicies.actionAll")}</option>
            <option value="NOTIFY_ONLY">{t("fleetPolicies.actionNotify")}</option>
            <option value="AUTO_BLOCK_CARD">{t("fleetPolicies.actionAutoBlock")}</option>
            <option value="ESCALATE_CASE">{t("fleetPolicies.actionEscalate")}</option>
          </select>
        </label>
        <label className="checkbox">
          <input type="checkbox" checked={activeOnly} onChange={(event) => setActiveOnly(event.target.checked)} />
          <span>{t("fleetPolicies.activeOnly")}</span>
        </label>
      </div>
      <Table
        columns={columns}
        data={filteredPolicies}
        emptyState={{
          title: t("fleetPolicies.emptyTitle"),
          description: t("fleetPolicies.emptyDescription"),
        }}
      />
      {showCreateModal ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-card">
            <h2>{t("fleetPolicies.createTitle")}</h2>
            <div className="form-grid">
              <div className="form-field">
                <span>{t("fleetPolicies.scope")}</span>
                {policyRole === "admin" ? (
                  <div className="checkbox-grid">
                    <label className="checkbox">
                      <input
                        type="radio"
                        name="scopeType"
                        value="CLIENT"
                        checked={scopeType === "CLIENT"}
                        onChange={() => {
                          setScopeType("CLIENT");
                          setScopeId("");
                        }}
                      />
                      <span>{t("fleetPolicies.scopeClient")}</span>
                    </label>
                    <label className="checkbox">
                      <input
                        type="radio"
                        name="scopeType"
                        value="GROUP"
                        checked={scopeType === "GROUP"}
                        onChange={() => {
                          setScopeType("GROUP");
                          setScopeId("");
                        }}
                      />
                      <span>{t("fleetPolicies.scopeGroup")}</span>
                    </label>
                    <label className="checkbox">
                      <input
                        type="radio"
                        name="scopeType"
                        value="CARD"
                        checked={scopeType === "CARD"}
                        onChange={() => {
                          setScopeType("CARD");
                          setScopeId("");
                        }}
                      />
                      <span>{t("fleetPolicies.scopeCard")}</span>
                    </label>
                  </div>
                ) : (
                  <div className="checkbox-grid">
                    <label className="checkbox">
                      <input type="radio" name="scopeType" value="GROUP" checked readOnly />
                      <span>{t("fleetPolicies.scopeGroup")}</span>
                    </label>
                  </div>
                )}
              </div>
              {scopeType === "GROUP" ? (
                <label className="form-field">
                  <span>{t("fleetPolicies.group")}</span>
                  <select value={scopeId} onChange={(event) => setScopeId(event.target.value)}>
                    <option value="">{t("fleetPolicies.scopeSelect")}</option>
                    {(policyRole === "admin" ? groups : manageableGroups).map((group) => (
                      <option key={group.id} value={group.id}>
                        {group.name}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
              {scopeType === "CARD" ? (
                <label className="form-field">
                  <span>{t("fleetPolicies.card")}</span>
                  <select value={scopeId} onChange={(event) => setScopeId(event.target.value)}>
                    <option value="">{t("fleetPolicies.scopeSelect")}</option>
                    {cards.map((card) => (
                      <option key={card.id} value={card.id}>
                        {card.card_alias ?? t("fleetPolicies.cardFallback")}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
              <label className="form-field">
                <span>{t("fleetPolicies.trigger")}</span>
                <select value={triggerType} onChange={(event) => setTriggerType(event.target.value)}>
                  <option value="">{t("fleetPolicies.triggerSelect")}</option>
                  <option value="LIMIT_BREACH">{t("fleetPolicies.triggerLimit")}</option>
                  <option value="ANOMALY">{t("fleetPolicies.triggerAnomaly")}</option>
                </select>
              </label>
              <label className="form-field">
                <span>{t("fleetPolicies.severityMin")}</span>
                <select value={severityMin} onChange={(event) => setSeverityMin(event.target.value)}>
                  <option value="">{t("fleetPolicies.severitySelect")}</option>
                  <option value="LOW">LOW</option>
                  <option value="MED">MED</option>
                  <option value="HIGH">HIGH</option>
                  <option value="CRIT">CRIT</option>
                </select>
              </label>
              {triggerType === "LIMIT_BREACH" ? (
                <label className="form-field">
                  <span>{t("fleetPolicies.breachKind")}</span>
                  <select value={breachKind} onChange={(event) => setBreachKind(event.target.value)}>
                    <option value="">{t("fleetPolicies.breachKindSelect")}</option>
                    <option value="HARD">{t("fleetPolicies.breachKindHard")}</option>
                    <option value="SOFT">{t("fleetPolicies.breachKindSoft")}</option>
                    <option value="ANY">{t("fleetPolicies.breachKindAny")}</option>
                  </select>
                </label>
              ) : null}
              <label className="form-field">
                <span>{t("fleetPolicies.action")}</span>
                <select value={action} onChange={(event) => setAction(event.target.value)}>
                  <option value="">{t("fleetPolicies.actionSelect")}</option>
                  <option value="NOTIFY_ONLY">{t("fleetPolicies.actionNotify")}</option>
                  <option value="AUTO_BLOCK_CARD">{t("fleetPolicies.actionAutoBlock")}</option>
                  <option value="ESCALATE_CASE">{t("fleetPolicies.actionEscalate")}</option>
                </select>
              </label>
              <label className="form-field">
                <span>{t("fleetPolicies.cooldown")}</span>
                <input value={cooldown} onChange={(event) => setCooldown(event.target.value)} type="number" min={60} />
              </label>
            </div>
            {action === "AUTO_BLOCK_CARD" ? <div className="warning-text">{t("fleetPolicies.autoBlockWarning")}</div> : null}
            {action === "ESCALATE_CASE" ? <div className="warning-text">{t("fleetPolicies.escalateWarning")}</div> : null}
            {formError ? <div className="error-text">{formError}</div> : null}
            <div className="actions">
              <button type="button" className="ghost" onClick={() => setShowCreateModal(false)}>
                {t("actions.comeBackLater")}
              </button>
              <button type="button" className="primary" onClick={() => void handleCreate()}>
                {t("fleetPolicies.submit")}
              </button>
            </div>
          </div>
        </div>
      ) : null}
      <ConfirmActionModal
        isOpen={!!disableTarget}
        title={t("fleetPolicies.disableTitle")}
        description={t("fleetPolicies.disableDescription")}
        confirmLabel={t("fleetPolicies.disableConfirm")}
        cancelLabel={t("actions.comeBackLater")}
        onConfirm={() => void handleDisable()}
        onCancel={() => setDisableTarget(null)}
      />
      <Toast toast={toast} />
    </div>
  );
}
