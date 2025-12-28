import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { cancelSubscription, createSubscription, listSubscriptions, pauseSubscription, resumeSubscription } from "../../api/crm";
import { useAuth } from "../../auth/AuthContext";
import { SubscriptionForm } from "../../components/crm/SubscriptionForm";
import { ConfirmModal } from "../../components/common/ConfirmModal";
import { DataTable, type DataColumn } from "../../components/common/DataTable";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import type { CrmSubscription } from "../../types/crm";
import { describeError, formatError } from "../../utils/apiErrors";

const actionLabels = {
  pause: "Pause",
  resume: "Resume",
  cancel: "Cancel",
};

const getNextRun = (billingDay?: number | null) => {
  if (!billingDay) return "-";
  const today = new Date();
  const run = new Date(today.getFullYear(), today.getMonth(), billingDay);
  if (run < today) {
    run.setMonth(run.getMonth() + 1);
  }
  return run.toISOString().slice(0, 10);
};

export const SubscriptionsPage: React.FC = () => {
  const navigate = useNavigate();
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [subscriptions, setSubscriptions] = useState<CrmSubscription[]>([]);
  const [loading, setLoading] = useState(false);
  const [clientFilter, setClientFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [saving, setSaving] = useState(false);
  const [canCreate, setCanCreate] = useState(true);
  const [confirmAction, setConfirmAction] = useState<null | { action: keyof typeof actionLabels; subscription: CrmSubscription }>(
    null,
  );
  const [actionVisibility, setActionVisibility] = useState<Record<keyof typeof actionLabels, boolean>>({
    pause: true,
    resume: true,
    cancel: true,
  });

  const loadSubscriptions = () => {
    if (!accessToken) return;
    setLoading(true);
    listSubscriptions(accessToken, { client_id: clientFilter || undefined, status: statusFilter || undefined })
      .then((response) => setSubscriptions(response.items))
      .catch((error: unknown) => showToast("error", formatError(error)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadSubscriptions();
  }, [accessToken, clientFilter, statusFilter]);

  const columns: DataColumn<CrmSubscription>[] = useMemo(
    () => [
      { key: "subscription_id", title: "Subscription", render: (row) => row.subscription_id ?? row.id ?? "-" },
      { key: "client_id", title: "Client" },
      { key: "tariff_id", title: "Tariff" },
      { key: "status", title: "Status", render: (row) => (row.status ? <StatusBadge status={row.status} /> : "-") },
      { key: "billing_day", title: "Billing day" },
      { key: "started_at", title: "Started" },
      { key: "next_run", title: "Next run", render: (row) => getNextRun(row.billing_day) },
    ],
    [],
  );

  const handleAction = async (action: keyof typeof actionLabels, subscription: CrmSubscription) => {
    if (!accessToken) return;
    const id = subscription.subscription_id ?? subscription.id ?? "";
    try {
      if (action === "pause") {
        await pauseSubscription(accessToken, id);
      }
      if (action === "resume") {
        await resumeSubscription(accessToken, id);
      }
      if (action === "cancel") {
        await cancelSubscription(accessToken, id);
      }
      showToast("success", `${actionLabels[action]} done`);
      loadSubscriptions();
    } catch (error: unknown) {
      const summary = describeError(error);
      if (summary.isForbidden) {
        setActionVisibility((prev) => ({ ...prev, [action]: false }));
      }
      showToast("error", formatError(error));
    } finally {
      setConfirmAction(null);
    }
  };

  const handleCreate = async (values: Partial<CrmSubscription>) => {
    if (!accessToken) return;
    const clientId = values.client_id ?? clientFilter;
    if (!clientId) {
      showToast("error", "Client ID is required");
      return;
    }
    setSaving(true);
    try {
      await createSubscription(accessToken, clientId, values);
      showToast("success", "Subscription created");
      setShowCreate(false);
      loadSubscriptions();
    } catch (error: unknown) {
      const summary = describeError(error);
      if (summary.isForbidden) {
        setCanCreate(false);
      }
      showToast("error", formatError(error));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <Toast toast={toast} />
      <h1>CRM · Subscriptions</h1>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
        <input placeholder="Client ID" value={clientFilter} onChange={(e) => setClientFilter(e.target.value)} />
        <input placeholder="Status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} />
        {canCreate && (
          <button type="button" onClick={() => setShowCreate((prev) => !prev)}>
            {showCreate ? "Close" : "Create subscription"}
          </button>
        )}
      </div>
      {showCreate && (
        <div style={{ marginBottom: 24, border: "1px solid #e2e8f0", padding: 16, borderRadius: 12 }}>
          <SubscriptionForm onSubmit={handleCreate} submitting={saving} submitLabel="Create" />
        </div>
      )}
      <DataTable
        data={subscriptions}
        columns={columns}
        loading={loading}
        onRowClick={(row) => navigate(`/crm/subscriptions/${row.subscription_id ?? row.id}`)}
      />

      <div style={{ marginTop: 16, display: "grid", gap: 8 }}>
        {subscriptions.map((subscription) => (
          <div key={subscription.subscription_id ?? subscription.id} style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <strong>{subscription.subscription_id ?? subscription.id}</strong>
            {actionVisibility.pause && (
              <button type="button" onClick={() => setConfirmAction({ action: "pause", subscription })}>
                Pause
              </button>
            )}
            {actionVisibility.resume && (
              <button type="button" onClick={() => setConfirmAction({ action: "resume", subscription })}>
                Resume
              </button>
            )}
            {actionVisibility.cancel && (
              <button type="button" onClick={() => setConfirmAction({ action: "cancel", subscription })}>
                Cancel
              </button>
            )}
            <button type="button" onClick={() => navigate(`/crm/subscriptions/${subscription.subscription_id ?? subscription.id}/preview-billing`)}>
              Preview billing
            </button>
          </div>
        ))}
      </div>

      <ConfirmModal
        open={Boolean(confirmAction)}
        title={confirmAction ? `${actionLabels[confirmAction.action]} subscription` : ""}
        description={confirmAction ? `Subscription ${confirmAction.subscription.subscription_id ?? ""}` : ""}
        danger={confirmAction?.action === "cancel"}
        onCancel={() => setConfirmAction(null)}
        onConfirm={() => {
          if (confirmAction) {
            void handleAction(confirmAction.action, confirmAction.subscription);
          }
        }}
      />
    </div>
  );
};

export default SubscriptionsPage;
