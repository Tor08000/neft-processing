import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { createSubscriptionPlan, listSubscriptionPlans } from "../../api/subscriptions";
import { useAuth } from "../../auth/AuthContext";
import { Table } from "../../components/Table/Table";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import type { SubscriptionPlan, SubscriptionPlanCreate } from "../../types/subscriptions";

export const SubscriptionPlansPage: React.FC = () => {
  const { accessToken } = useAuth();
  const navigate = useNavigate();
  const { toast, showToast } = useToast();
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [draft, setDraft] = useState<SubscriptionPlanCreate>({
    code: "",
    title: "",
    description: "",
    is_active: true,
    billing_period_months: 1,
    price_cents: 0,
    currency: "RUB",
  });

  const loadPlans = () => {
    if (!accessToken) return;
    setLoading(true);
    listSubscriptionPlans(accessToken)
      .then(setPlans)
      .catch((error: unknown) => showToast("error", String(error)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadPlans();
  }, [accessToken]);

  const handleCreate = async () => {
    if (!accessToken) return;
    if (!draft.code || !draft.title) {
      showToast("error", "Code and title are required");
      return;
    }
    setSaving(true);
    try {
      await createSubscriptionPlan(accessToken, draft);
      setDraft({
        code: "",
        title: "",
        description: "",
        is_active: true,
        billing_period_months: 1,
        price_cents: 0,
        currency: "RUB",
      });
      showToast("success", "Plan created");
      loadPlans();
    } catch (error: unknown) {
      showToast("error", String(error));
    } finally {
      setSaving(false);
    }
  };

  const columns = useMemo(
    () => [
      { key: "code", title: "Code", dataIndex: "code" as const },
      { key: "title", title: "Title", dataIndex: "title" as const },
      { key: "period", title: "Period (months)", render: (row: SubscriptionPlan) => row.billing_period_months },
      { key: "price", title: "Price (cents)", render: (row: SubscriptionPlan) => row.price_cents },
      { key: "status", title: "Active", render: (row: SubscriptionPlan) => (row.is_active ? "Yes" : "No") },
    ],
    [],
  );

  return (
    <div>
      <Toast toast={toast} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h1>Subscriptions · Plans</h1>
      </div>

      <div className="card" style={{ padding: 16, marginBottom: 16 }}>
        <h3>Create plan</h3>
        <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
          <label>
            Code
            <input
              className="neft-input"
              value={draft.code}
              onChange={(event) => setDraft((prev) => ({ ...prev, code: event.target.value.toUpperCase() }))}
            />
          </label>
          <label>
            Title
            <input
              className="neft-input"
              value={draft.title}
              onChange={(event) => setDraft((prev) => ({ ...prev, title: event.target.value }))}
            />
          </label>
          <label>
            Billing period
            <input
              className="neft-input"
              type="number"
              value={draft.billing_period_months}
              onChange={(event) =>
                setDraft((prev) => ({ ...prev, billing_period_months: Number(event.target.value) }))
              }
            />
          </label>
          <label>
            Price (cents)
            <input
              className="neft-input"
              type="number"
              value={draft.price_cents}
              onChange={(event) => setDraft((prev) => ({ ...prev, price_cents: Number(event.target.value) }))}
            />
          </label>
          <label>
            Currency
            <input
              className="neft-input"
              value={draft.currency}
              onChange={(event) => setDraft((prev) => ({ ...prev, currency: event.target.value }))}
            />
          </label>
          <label>
            Active
            <select
              className="neft-input"
              value={draft.is_active ? "true" : "false"}
              onChange={(event) => setDraft((prev) => ({ ...prev, is_active: event.target.value === "true" }))}
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
            value={draft.description ?? ""}
            onChange={(event) => setDraft((prev) => ({ ...prev, description: event.target.value }))}
          />
        </label>
        <button className="neft-btn" type="button" onClick={handleCreate} disabled={saving} style={{ marginTop: 12 }}>
          {saving ? "Saving..." : "Create"}
        </button>
      </div>

      <Table
        columns={columns}
        data={plans}
        loading={loading}
        emptyMessage="No plans yet"
        onRowClick={(row) => navigate(`/subscriptions/plans/${row.id}`)}
      />
    </div>
  );
};

export default SubscriptionPlansPage;
