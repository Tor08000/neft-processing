import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import {
  assignSubscription,
  createBonusRule,
  getClientSubscription,
  getSubscriptionPlan,
  listBonusRules,
  updateBonusRule,
  updateSubscriptionPlan,
  updateSubscriptionPlanModules,
  updateSubscriptionPlanRoles,
} from "../../api/subscriptions";
import { useAuth } from "../../auth/AuthContext";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import type {
  AssignSubscriptionPayload,
  BonusRule,
  ClientSubscription,
  RoleEntitlement,
  SubscriptionPlan,
  SubscriptionPlanModule,
  SubscriptionPlanUpdate,
} from "../../types/subscriptions";

const MODULES: SubscriptionPlanModule["module_code"][] = [
  "FUEL_CORE",
  "AI_ASSISTANT",
  "EXPLAIN",
  "PENALTIES",
  "MARKETPLACE",
  "ANALYTICS",
  "SLA",
  "BONUSES",
];

const ROLES = ["OWNER", "MANAGER", "ACCOUNTANT", "DRIVER", "ANALYST"];

const formatJson = (value: Record<string, unknown> | null | undefined) =>
  value ? JSON.stringify(value, null, 2) : "";

const parseJson = (raw: string) => {
  if (!raw.trim()) return null;
  return JSON.parse(raw);
};

export const SubscriptionPlanDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [plan, setPlan] = useState<SubscriptionPlan | null>(null);
  const [modules, setModules] = useState<SubscriptionPlanModule[]>([]);
  const [roles, setRoles] = useState<Record<string, string>>({});
  const [bonusRules, setBonusRules] = useState<BonusRule[]>([]);
  const [moduleLimits, setModuleLimits] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [clientId, setClientId] = useState("");
  const [assignPayload, setAssignPayload] = useState<AssignSubscriptionPayload>({
    plan_id: id ?? "",
    duration_months: 1,
    auto_renew: true,
  });
  const [clientSubscription, setClientSubscription] = useState<ClientSubscription | null>(null);
  const [bonusDraft, setBonusDraft] = useState({
    rule_code: "",
    title: "",
    condition: "{}",
    reward: "{}",
    enabled: true,
  });

  const loadPlan = () => {
    if (!accessToken || !id) return;
    setLoading(true);
    Promise.all([getSubscriptionPlan(accessToken, id), listBonusRules(accessToken, id)])
      .then(([planResponse, bonusResponse]) => {
        setPlan(planResponse);
        const initialModules = MODULES.map(
          (code) =>
            planResponse.modules?.find((module) => module.module_code === code) ?? {
              module_code: code,
              enabled: false,
              tier: "",
              limits: {},
            },
        );
        setModules(initialModules);
        const limitsMap: Record<string, string> = {};
        initialModules.forEach((module) => {
          limitsMap[module.module_code] = formatJson(module.limits ?? {});
        });
        setModuleLimits(limitsMap);
        const roleMap: Record<string, string> = {};
        planResponse.roles?.forEach((role) => {
          roleMap[role.role_code] = formatJson(role.entitlements);
        });
        setRoles(roleMap);
        setBonusRules(bonusResponse);
      })
      .catch((error: unknown) => showToast("error", String(error)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadPlan();
  }, [accessToken, id]);

  const handlePlanUpdate = async (payload: SubscriptionPlanUpdate) => {
    if (!accessToken || !id) return;
    setSaving(true);
    try {
      const updated = await updateSubscriptionPlan(accessToken, id, payload);
      setPlan(updated);
      showToast("success", "Plan updated");
    } catch (error: unknown) {
      showToast("error", String(error));
    } finally {
      setSaving(false);
    }
  };

  const handleModulesSave = async () => {
    if (!accessToken || !id) return;
    setSaving(true);
    try {
      const payload = modules.map((module) => ({
        ...module,
        limits: parseJson(moduleLimits[module.module_code] ?? ""),
      }));
      const updated = await updateSubscriptionPlanModules(accessToken, id, payload);
      setModules(updated);
      showToast("success", "Modules updated");
    } catch (error: unknown) {
      showToast("error", "Invalid JSON in module limits");
    } finally {
      setSaving(false);
    }
  };

  const handleRolesSave = async () => {
    if (!accessToken || !id) return;
    setSaving(true);
    try {
      const payload: RoleEntitlement[] = ROLES.map((role) => ({
        role_code: role,
        entitlements: parseJson(roles[role] ?? ""),
      }));
      await updateSubscriptionPlanRoles(accessToken, id, payload);
      showToast("success", "Roles updated");
    } catch (error: unknown) {
      showToast("error", "Invalid JSON in role entitlements");
    } finally {
      setSaving(false);
    }
  };

  const handleAssign = async () => {
    if (!accessToken || !clientId || !id) return;
    try {
      const assigned = await assignSubscription(accessToken, clientId, { ...assignPayload, plan_id: id });
      setClientSubscription(assigned);
      showToast("success", "Subscription assigned");
    } catch (error: unknown) {
      showToast("error", String(error));
    }
  };

  const handleLoadClientSubscription = async () => {
    if (!accessToken || !clientId) return;
    try {
      const subscription = await getClientSubscription(accessToken, clientId);
      setClientSubscription(subscription);
    } catch (error: unknown) {
      showToast("error", String(error));
    }
  };

  const handleBonusCreate = async () => {
    if (!accessToken || !id) return;
    try {
      const rule = await createBonusRule(accessToken, {
        plan_id: id,
        rule_code: bonusDraft.rule_code,
        title: bonusDraft.title,
        condition: parseJson(bonusDraft.condition),
        reward: parseJson(bonusDraft.reward),
        enabled: bonusDraft.enabled,
      });
      setBonusRules((prev) => [rule, ...prev]);
      setBonusDraft({ rule_code: "", title: "", condition: "{}", reward: "{}", enabled: true });
      showToast("success", "Bonus rule created");
    } catch (error: unknown) {
      showToast("error", "Invalid bonus rule payload");
    }
  };

  const handleToggleBonus = async (rule: BonusRule) => {
    if (!accessToken) return;
    try {
      const updated = await updateBonusRule(accessToken, rule.id, { enabled: !rule.enabled });
      setBonusRules((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
    } catch (error: unknown) {
      showToast("error", String(error));
    }
  };

  const moduleRows = useMemo(() => {
    return MODULES.map((code) => modules.find((item) => item.module_code === code) ?? { module_code: code, enabled: false });
  }, [modules]);

  if (loading) {
    return <div>Loading...</div>;
  }

  if (!plan) {
    return <div>Plan not found</div>;
  }

  return (
    <div>
      <Toast toast={toast} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>Subscriptions · {plan.title}</h1>
        <button className="neft-btn-secondary" type="button" onClick={() => navigate("/subscriptions/plans")}>Back</button>
      </div>

      <div className="card" style={{ padding: 16, marginTop: 16 }}>
        <h3>Plan details</h3>
        <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
          <label>
            Title
            <input
              className="neft-input"
              value={plan.title}
              onChange={(event) => setPlan((prev) => (prev ? { ...prev, title: event.target.value } : prev))}
            />
          </label>
          <label>
            Code
            <input
              className="neft-input"
              value={plan.code}
              onChange={(event) => setPlan((prev) => (prev ? { ...prev, code: event.target.value } : prev))}
            />
          </label>
          <label>
            Billing period
            <input
              className="neft-input"
              type="number"
              value={plan.billing_period_months}
              onChange={(event) =>
                setPlan((prev) => (prev ? { ...prev, billing_period_months: Number(event.target.value) } : prev))
              }
            />
          </label>
          <label>
            Price (cents)
            <input
              className="neft-input"
              type="number"
              value={plan.price_cents}
              onChange={(event) => setPlan((prev) => (prev ? { ...prev, price_cents: Number(event.target.value) } : prev))}
            />
          </label>
          <label>
            Currency
            <input
              className="neft-input"
              value={plan.currency}
              onChange={(event) => setPlan((prev) => (prev ? { ...prev, currency: event.target.value } : prev))}
            />
          </label>
          <label>
            Active
            <select
              className="neft-input"
              value={plan.is_active ? "true" : "false"}
              onChange={(event) => setPlan((prev) => (prev ? { ...prev, is_active: event.target.value === "true" } : prev))}
            >
              <option value="true">Active</option>
              <option value="false">Inactive</option>
            </select>
          </label>
        </div>
        <label style={{ marginTop: 12, display: "block" }}>
          Description
          <textarea
            className="neft-input"
            value={plan.description ?? ""}
            onChange={(event) => setPlan((prev) => (prev ? { ...prev, description: event.target.value } : prev))}
          />
        </label>
        <button
          className="neft-btn"
          type="button"
          onClick={() =>
            handlePlanUpdate({
              code: plan.code,
              title: plan.title,
              description: plan.description,
              is_active: plan.is_active,
              billing_period_months: plan.billing_period_months,
              price_cents: plan.price_cents,
              currency: plan.currency,
            })
          }
          disabled={saving}
          style={{ marginTop: 12 }}
        >
          Save plan
        </button>
      </div>

      <div className="card" style={{ padding: 16, marginTop: 16 }}>
        <h3>Modules & limits</h3>
        <div style={{ display: "grid", gap: 12 }}>
          {moduleRows.map((module) => (
            <div key={module.module_code} style={{ borderBottom: "1px solid #e2e8f0", paddingBottom: 12 }}>
              <strong>{module.module_code}</strong>
              <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
                <label>
                  Enabled
                  <select
                    className="neft-input"
                    value={module.enabled ? "true" : "false"}
                    onChange={(event) => {
                      const enabled = event.target.value === "true";
                      setModules((prev) => {
                        const next = prev.filter((item) => item.module_code !== module.module_code);
                        next.push({ ...module, enabled });
                        return next;
                      });
                    }}
                  >
                    <option value="true">Enabled</option>
                    <option value="false">Disabled</option>
                  </select>
                </label>
                <label>
                  Tier
                  <input
                    className="neft-input"
                    value={module.tier ?? ""}
                    onChange={(event) => {
                      const tier = event.target.value;
                      setModules((prev) => {
                        const next = prev.filter((item) => item.module_code !== module.module_code);
                        next.push({ ...module, tier });
                        return next;
                      });
                    }}
                  />
                </label>
                <label>
                  Limits (JSON)
                  <textarea
                    className="neft-input"
                    value={moduleLimits[module.module_code] ?? ""}
                    onChange={(event) => {
                      const raw = event.target.value;
                      setModuleLimits((prev) => ({ ...prev, [module.module_code]: raw }));
                    }}
                  />
                </label>
              </div>
            </div>
          ))}
        </div>
        <button className="neft-btn" type="button" onClick={handleModulesSave} disabled={saving} style={{ marginTop: 12 }}>
          Save modules
        </button>
      </div>

      <div className="card" style={{ padding: 16, marginTop: 16 }}>
        <h3>Role entitlements</h3>
        <div style={{ display: "grid", gap: 12 }}>
          {ROLES.map((role) => (
            <label key={role}>
              {role} (JSON)
              <textarea
                className="neft-input"
                value={roles[role] ?? ""}
                onChange={(event) => setRoles((prev) => ({ ...prev, [role]: event.target.value }))}
              />
            </label>
          ))}
        </div>
        <button className="neft-btn" type="button" onClick={handleRolesSave} disabled={saving} style={{ marginTop: 12 }}>
          Save roles
        </button>
      </div>

      <div className="card" style={{ padding: 16, marginTop: 16 }}>
        <h3>Bonus rules</h3>
        <div style={{ display: "grid", gap: 12 }}>
          {bonusRules.map((rule) => (
            <div key={rule.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <strong>{rule.rule_code}</strong> — {rule.title}
              </div>
              <button className="neft-btn-secondary" type="button" onClick={() => handleToggleBonus(rule)}>
                {rule.enabled ? "Disable" : "Enable"}
              </button>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 12, display: "grid", gap: 12 }}>
          <h4>Create bonus rule</h4>
          <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
            <label>
              Code
              <input
                className="neft-input"
                value={bonusDraft.rule_code}
                onChange={(event) => setBonusDraft((prev) => ({ ...prev, rule_code: event.target.value }))}
              />
            </label>
            <label>
              Title
              <input
                className="neft-input"
                value={bonusDraft.title}
                onChange={(event) => setBonusDraft((prev) => ({ ...prev, title: event.target.value }))}
              />
            </label>
            <label>
              Condition (JSON)
              <textarea
                className="neft-input"
                value={bonusDraft.condition}
                onChange={(event) => setBonusDraft((prev) => ({ ...prev, condition: event.target.value }))}
              />
            </label>
            <label>
              Reward (JSON)
              <textarea
                className="neft-input"
                value={bonusDraft.reward}
                onChange={(event) => setBonusDraft((prev) => ({ ...prev, reward: event.target.value }))}
              />
            </label>
            <label>
              Enabled
              <select
                className="neft-input"
                value={bonusDraft.enabled ? "true" : "false"}
                onChange={(event) => setBonusDraft((prev) => ({ ...prev, enabled: event.target.value === "true" }))}
              >
                <option value="true">Enabled</option>
                <option value="false">Disabled</option>
              </select>
            </label>
          </div>
          <button className="neft-btn" type="button" onClick={handleBonusCreate}>
            Add bonus rule
          </button>
        </div>
      </div>

      <div className="card" style={{ padding: 16, marginTop: 16 }}>
        <h3>Assign plan to client</h3>
        <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
          <label>
            Client ID
            <input className="neft-input" value={clientId} onChange={(event) => setClientId(event.target.value)} />
          </label>
          <label>
            Duration (months)
            <input
              className="neft-input"
              type="number"
              value={assignPayload.duration_months ?? 1}
              onChange={(event) =>
                setAssignPayload((prev) => ({ ...prev, duration_months: Number(event.target.value) }))
              }
            />
          </label>
          <label>
            Auto-renew
            <select
              className="neft-input"
              value={assignPayload.auto_renew ? "true" : "false"}
              onChange={(event) => setAssignPayload((prev) => ({ ...prev, auto_renew: event.target.value === "true" }))}
            >
              <option value="true">Enabled</option>
              <option value="false">Disabled</option>
            </select>
          </label>
        </div>
        <div style={{ display: "flex", gap: 12, marginTop: 12 }}>
          <button className="neft-btn" type="button" onClick={handleAssign}>
            Assign
          </button>
          <button className="neft-btn-secondary" type="button" onClick={handleLoadClientSubscription}>
            Load current
          </button>
        </div>
        {clientSubscription ? (
          <div style={{ marginTop: 12 }}>
            <div>
              Current status: <strong>{clientSubscription.status}</strong>
            </div>
            <div>Plan: {clientSubscription.plan?.code ?? clientSubscription.plan_id}</div>
            <div>Period: {clientSubscription.start_at} → {clientSubscription.end_at ?? "—"}</div>
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default SubscriptionPlanDetailsPage;
