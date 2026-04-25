import React, { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getSubscription, updateSubscription } from "../../api/crm";
import { useAuth } from "../../auth/AuthContext";
import { EmptyState } from "../../components/common/EmptyState";
import { ErrorState } from "../../components/common/ErrorState";
import { JsonViewer } from "../../components/common/JsonViewer";
import { Loader } from "../../components/Loader/Loader";
import { Toast } from "../../components/common/Toast";
import { SubscriptionForm } from "../../components/crm/SubscriptionForm";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import { useToast } from "../../components/Toast/useToast";
import type { CrmSubscription } from "../../types/crm";
import { describeError, formatError } from "../../utils/apiErrors";

const EMPTY_VALUE = "-";

export const SubscriptionDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [subscription, setSubscription] = useState<CrmSubscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadErrorDetails, setLoadErrorDetails] = useState<string | undefined>(undefined);
  const [periodId, setPeriodId] = useState("");
  const [saving, setSaving] = useState(false);

  const loadSubscription = useCallback(() => {
    if (!accessToken || !id) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setLoadError(null);
    setLoadErrorDetails(undefined);
    setSubscription(null);
    getSubscription(accessToken, id)
      .then((response) => {
        setSubscription(response);
      })
      .catch((error: unknown) => {
        const summary = describeError(error);
        setLoadError(summary.message);
        setLoadErrorDetails(summary.details);
        showToast("error", formatError(error));
      })
      .finally(() => setLoading(false));
  }, [accessToken, id, showToast]);

  useEffect(() => {
    loadSubscription();
  }, [loadSubscription]);

  const handleUpdate = async (values: Partial<CrmSubscription>) => {
    if (!accessToken || !subscription) return;
    const subscriptionId = subscription.subscription_id ?? subscription.id ?? "";
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

  if (loading) {
    return <Loader label="Loading subscription detail" />;
  }

  if (!id) {
    return (
      <EmptyState
        title="Subscription ID is required"
        description="Open the subscription detail page from the CRM subscriptions list."
        primaryAction={{ label: "Back to subscriptions", onClick: () => navigate("/crm/subscriptions") }}
      />
    );
  }

  if (loadError) {
    return (
      <ErrorState
        title="Failed to load subscription detail"
        description={loadError}
        details={loadErrorDetails}
        actionLabel="Retry"
        onAction={() => void loadSubscription()}
      />
    );
  }

  if (!subscription) {
    return (
      <EmptyState
        title="Subscription not found"
        description="The requested subscription is missing or no longer available."
        primaryAction={{ label: "Back to subscriptions", onClick: () => navigate("/crm/subscriptions") }}
      />
    );
  }

  const subscriptionId = subscription.subscription_id ?? subscription.id ?? "";

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
          <button
            type="button"
            onClick={() => navigate(`/crm/subscriptions/${subscriptionId}/preview-billing?period_id=${periodId}`)}
            disabled={!periodId}
          >
            Preview billing
          </button>
          <button
            type="button"
            onClick={() =>
              navigate(
                `/crm/subscriptions/${subscriptionId}/cfo-explain${periodId ? `?period_id=${periodId}` : ""}`,
              )
            }
            disabled={!periodId}
          >
            CFO explain
          </button>
        </div>
      </div>
      <div style={{ display: "grid", gap: 16 }}>
        <div style={{ display: "grid", gap: 8 }}>
          <div>Status: {subscription.status ? <StatusBadge status={subscription.status} /> : EMPTY_VALUE}</div>
          <div>Client: {subscription.client_id ?? EMPTY_VALUE}</div>
          <div>Tariff: {subscription.tariff_plan_id ?? EMPTY_VALUE}</div>
          <div>Billing cycle: {subscription.billing_cycle ?? EMPTY_VALUE}</div>
          <div>Billing day: {subscription.billing_day ?? EMPTY_VALUE}</div>
          <div>Started at: {subscription.started_at ?? EMPTY_VALUE}</div>
          <div>Paused at: {subscription.paused_at ?? EMPTY_VALUE}</div>
          <div>Ended at: {subscription.ended_at ?? EMPTY_VALUE}</div>
        </div>
        <div style={{ border: "1px solid #e2e8f0", padding: 16, borderRadius: 12 }}>
          <h3>Edit subscription</h3>
          <SubscriptionForm
            initialValues={subscription}
            onSubmit={handleUpdate}
            submitting={saving}
            submitLabel="Update"
            showClientId={false}
            showTenantId={false}
            showTariffPlanId={false}
          />
        </div>
        <JsonViewer value={subscription} title="Subscription payload" />
      </div>
    </div>
  );
};

export default SubscriptionDetailsPage;
