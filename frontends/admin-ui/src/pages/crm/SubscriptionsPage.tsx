import React, { useCallback, useEffect, useMemo, useState } from "react";
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
import { subscriptionsPageCopy } from "./crmListPageCopy";

const getNextRun = (billingDay?: number | null) => {
  if (!billingDay) return subscriptionsPageCopy.values.fallback;
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
  const [error, setError] = useState<{ title: string; description?: string; details?: string } | null>(null);
  const [clientFilter, setClientFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [saving, setSaving] = useState(false);
  const [canCreate, setCanCreate] = useState(true);
  const [confirmAction, setConfirmAction] = useState<null | { action: keyof typeof subscriptionsPageCopy.actionLabels; subscription: CrmSubscription }>(
    null,
  );
  const [actionVisibility, setActionVisibility] = useState<Record<keyof typeof subscriptionsPageCopy.actionLabels, boolean>>({
    pause: true,
    resume: true,
    cancel: true,
  });
  const filtersActive = Boolean(clientFilter.trim() || statusFilter.trim());

  const loadSubscriptions = useCallback(() => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    listSubscriptions(accessToken, { client_id: clientFilter || undefined, status: statusFilter || undefined })
      .then((response) => setSubscriptions(response.items))
      .catch((error: unknown) => {
        const summary = describeError(error);
        setError({ title: subscriptionsPageCopy.errors.load, description: summary.message, details: summary.details });
        showToast("error", formatError(error));
      })
      .finally(() => setLoading(false));
  }, [accessToken, clientFilter, showToast, statusFilter]);

  useEffect(() => {
    loadSubscriptions();
  }, [accessToken, clientFilter, loadSubscriptions, statusFilter]);

  const columns: DataColumn<CrmSubscription>[] = useMemo(
    () => [
      { key: "subscription_id", title: subscriptionsPageCopy.columns.subscription, render: (row) => row.id },
      { key: "client_id", title: subscriptionsPageCopy.columns.client },
      { key: "tariff_plan_id", title: subscriptionsPageCopy.columns.tariff },
      {
        key: "status",
        title: subscriptionsPageCopy.columns.status,
        render: (row) => (row.status ? <StatusBadge status={row.status} /> : subscriptionsPageCopy.values.fallback),
      },
      { key: "billing_day", title: subscriptionsPageCopy.columns.billingDay },
      { key: "started_at", title: subscriptionsPageCopy.columns.started },
      { key: "next_run", title: subscriptionsPageCopy.columns.nextRun, render: (row) => getNextRun(row.billing_day) },
      {
        key: "actions",
        title: subscriptionsPageCopy.columns.actions,
        render: (row) => (
          <div className="table-row-actions">
            {actionVisibility.pause ? (
              <button
                type="button"
                className="ghost"
                onClick={(event) => {
                  event.stopPropagation();
                  setConfirmAction({ action: "pause", subscription: row });
                }}
              >
                {subscriptionsPageCopy.actionLabels.pause}
              </button>
            ) : null}
            {actionVisibility.resume ? (
              <button
                type="button"
                className="ghost"
                onClick={(event) => {
                  event.stopPropagation();
                  setConfirmAction({ action: "resume", subscription: row });
                }}
              >
                {subscriptionsPageCopy.actionLabels.resume}
              </button>
            ) : null}
            {actionVisibility.cancel ? (
              <button
                type="button"
                className="ghost"
                onClick={(event) => {
                  event.stopPropagation();
                  setConfirmAction({ action: "cancel", subscription: row });
                }}
              >
                {subscriptionsPageCopy.actionLabels.cancel}
              </button>
            ) : null}
            <button
              type="button"
              className="ghost"
              onClick={(event) => {
                event.stopPropagation();
                navigate(`/crm/subscriptions/${row.id}/preview-billing`);
              }}
            >
              {subscriptionsPageCopy.actions.previewBilling}
            </button>
          </div>
        ),
      },
    ],
    [actionVisibility, navigate],
  );

  const handleAction = async (action: keyof typeof subscriptionsPageCopy.actionLabels, subscription: CrmSubscription) => {
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
      showToast("success", subscriptionsPageCopy.toasts.done(subscriptionsPageCopy.actionLabels[action]));
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
      showToast("error", subscriptionsPageCopy.errors.clientIdRequired);
      return;
    }
    setSaving(true);
    try {
      await createSubscription(accessToken, clientId, values);
      showToast("success", subscriptionsPageCopy.toasts.created);
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
      <h1>{subscriptionsPageCopy.title}</h1>
      {showCreate && (
        <div style={{ marginBottom: 24, border: "1px solid #e2e8f0", padding: 16, borderRadius: 12 }}>
          <SubscriptionForm onSubmit={handleCreate} submitting={saving} submitLabel="Create" />
        </div>
      )}
      <DataTable
        data={subscriptions}
        columns={columns}
        loading={loading}
        toolbar={
          <div className="table-toolbar">
            <div className="filters">
              <div className="filter">
                <label className="label" htmlFor="crm-subscription-client-filter">
                  {subscriptionsPageCopy.labels.clientId}
                </label>
                <input
                  id="crm-subscription-client-filter"
                  placeholder={subscriptionsPageCopy.placeholders.clientId}
                  value={clientFilter}
                  onChange={(e) => setClientFilter(e.target.value)}
                />
              </div>
              <div className="filter">
                <label className="label" htmlFor="crm-subscription-status-filter">
                  {subscriptionsPageCopy.labels.status}
                </label>
                <input
                  id="crm-subscription-status-filter"
                  placeholder={subscriptionsPageCopy.placeholders.status}
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                />
              </div>
            </div>
            <div className="toolbar-actions">
              <button
                type="button"
                className="button secondary"
                onClick={() => {
                  setClientFilter("");
                  setStatusFilter("");
                }}
                disabled={!filtersActive}
              >
                {subscriptionsPageCopy.actions.reset}
              </button>
              {canCreate ? (
                <button type="button" className="button primary" onClick={() => setShowCreate((prev) => !prev)}>
                  {showCreate ? subscriptionsPageCopy.actions.close : subscriptionsPageCopy.actions.create}
                </button>
              ) : null}
            </div>
          </div>
        }
        errorState={
          error
            ? {
                title: error.title,
                description: error.description,
                details: error.details,
                actionLabel: subscriptionsPageCopy.actions.retry,
                actionOnClick: loadSubscriptions,
              }
            : undefined
        }
        footer={<div className="table-footer__content muted">{subscriptionsPageCopy.footer.rows(subscriptions.length)}</div>}
        emptyState={{
          title: filtersActive ? subscriptionsPageCopy.empty.filteredTitle : subscriptionsPageCopy.empty.pristineTitle,
          description: filtersActive
            ? subscriptionsPageCopy.empty.filteredDescription
            : subscriptionsPageCopy.empty.pristineDescription,
          actionLabel:
            filtersActive ? subscriptionsPageCopy.empty.resetAction : canCreate ? subscriptionsPageCopy.actions.create : undefined,
          actionOnClick: filtersActive
            ? () => {
                setClientFilter("");
                setStatusFilter("");
              }
            : canCreate
              ? () => setShowCreate(true)
              : undefined,
        }}
        onRowClick={(row) => navigate(`/crm/subscriptions/${row.id}`)}
      />

      <ConfirmModal
        open={Boolean(confirmAction)}
        title={
          confirmAction
            ? subscriptionsPageCopy.confirm.title(subscriptionsPageCopy.actionLabels[confirmAction.action])
            : ""
        }
        description={
          confirmAction
            ? subscriptionsPageCopy.confirm.description(confirmAction.subscription.subscription_id ?? "")
            : ""
        }
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
