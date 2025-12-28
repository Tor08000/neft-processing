import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getSubscription, updateSubscription } from "../../api/crm";
import { useAuth } from "../../auth/AuthContext";
import { SubscriptionForm } from "../../components/crm/SubscriptionForm";
import { JsonViewer } from "../../components/common/JsonViewer";
import { Tabs } from "../../components/common/Tabs";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import type { CrmSubscription } from "../../types/crm";
import { formatError } from "../../utils/apiErrors";

export const SubscriptionDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [subscription, setSubscription] = useState<CrmSubscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("overview");
  const [periodId, setPeriodId] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!accessToken || !id) return;
    setLoading(true);
    getSubscription(accessToken, id)
      .then((response) => {
        setSubscription(response);
        setPeriodId(response.last_period_id ?? "");
      })
      .catch((error: unknown) => showToast("error", formatError(error)))
      .finally(() => setLoading(false));
  }, [accessToken, id, showToast]);

  if (loading) {
    return <div>Loading...</div>;
  }

  if (!subscription) {
    return <div>Subscription not found</div>;
  }

  const subscriptionId = subscription.subscription_id ?? subscription.id ?? "";

  const handleUpdate = async (values: Partial<CrmSubscription>) => {
    if (!accessToken) return;
    setSaving(true);
    try {
      const updated = await updateSubscription(accessToken, subscriptionId, values);
      setSubscription(updated);
      showToast("success", "Subscription updated");
    } catch (error: unknown) {
      showToast("error", formatError(error));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <Toast toast={toast} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16 }}>
        <h1>Subscription {subscriptionId}</h1>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <input
            placeholder="Period ID"
            value={periodId}
            onChange={(event) => setPeriodId(event.target.value)}
            style={{ minWidth: 180 }}
          />
          <button type="button" onClick={() => navigate(`/crm/subscriptions/${subscriptionId}/preview-billing`)}>
            Preview billing
          </button>
          <button
            type="button"
            onClick={() =>
              navigate(
                `/crm/subscriptions/${subscriptionId}/cfo-explain${periodId ? `?period_id=${periodId}` : ""}`,
              )
            }
          >
            CFO explain
          </button>
        </div>
      </div>

      <Tabs
        tabs={[
          { id: "overview", label: "Overview" },
          { id: "segments", label: "Segments" },
          { id: "usage", label: "Usage" },
          { id: "charges", label: "Charges" },
          { id: "invoices", label: "Invoice links" },
          { id: "money", label: "Money links" },
        ]}
        active={tab}
        onChange={setTab}
      />

      {tab === "overview" && (
        <div style={{ display: "grid", gap: 16 }}>
          <div style={{ display: "grid", gap: 8 }}>
            <div>Status: {subscription.status ? <StatusBadge status={subscription.status} /> : "-"}</div>
            <div>Client: {subscription.client_id ?? "-"}</div>
            <div>Tariff: {subscription.tariff_id ?? "-"}</div>
            <div>Billing day: {subscription.billing_day ?? "-"}</div>
            <div>Started at: {subscription.started_at ?? "-"}</div>
          </div>
          <div style={{ border: "1px solid #e2e8f0", padding: 16, borderRadius: 12 }}>
            <h3>Edit subscription</h3>
            <SubscriptionForm initialValues={subscription} onSubmit={handleUpdate} submitting={saving} submitLabel="Update" />
          </div>
        </div>
      )}

      {tab === "segments" && (
        <JsonViewer value={subscription.segments ?? []} title="Segments" />
      )}

      {tab === "usage" && (
        <JsonViewer value={subscription.usage ?? []} title="Usage" />
      )}

      {tab === "charges" && (
        <JsonViewer value={subscription.charges ?? []} title="Charges" />
      )}

      {tab === "invoices" && (
        <div style={{ display: "grid", gap: 8 }}>
          {(subscription.invoices ?? []).length === 0 && <div>Нет invoice ссылок</div>}
          {(subscription.invoices ?? []).map((invoiceId) => (
            <button key={invoiceId} type="button" onClick={() => navigate(`/billing/invoices/${invoiceId}`)}>
              Invoice {invoiceId}
            </button>
          ))}
        </div>
      )}

      {tab === "money" && (
        <JsonViewer value={subscription.money_links ?? []} title="Money links" />
      )}
    </div>
  );
};

export default SubscriptionDetailsPage;
