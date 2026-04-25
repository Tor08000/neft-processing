import React, { useEffect, useState } from "react";
import type { CrmSubscription } from "../../types/crm";

interface SubscriptionFormProps {
  initialValues?: Partial<CrmSubscription>;
  onSubmit: (values: Partial<CrmSubscription>) => void | Promise<void>;
  submitting?: boolean;
  submitLabel?: string;
  showClientId?: boolean;
  showTenantId?: boolean;
  showTariffPlanId?: boolean;
}

const toDateInput = (value?: string | null) => (value ? value.slice(0, 10) : "");

export const SubscriptionForm: React.FC<SubscriptionFormProps> = ({
  initialValues,
  onSubmit,
  submitting,
  submitLabel = "Сохранить",
  showClientId = true,
  showTenantId = true,
  showTariffPlanId = true,
}) => {
  const [tenantId, setTenantId] = useState(String(initialValues?.tenant_id ?? ""));
  const [clientId, setClientId] = useState(initialValues?.client_id ?? "");
  const [tariffPlanId, setTariffPlanId] = useState(initialValues?.tariff_plan_id ?? "");
  const [billingDay, setBillingDay] = useState(String(initialValues?.billing_day ?? ""));
  const [startedAt, setStartedAt] = useState(toDateInput(initialValues?.started_at));

  useEffect(() => {
    setTenantId(String(initialValues?.tenant_id ?? ""));
    setClientId(initialValues?.client_id ?? "");
    setTariffPlanId(initialValues?.tariff_plan_id ?? "");
    setBillingDay(String(initialValues?.billing_day ?? ""));
    setStartedAt(toDateInput(initialValues?.started_at));
  }, [initialValues]);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    onSubmit({
      tenant_id: tenantId ? Number(tenantId) : undefined,
      client_id: clientId,
      tariff_plan_id: tariffPlanId,
      billing_day: billingDay ? Number(billingDay) : undefined,
      started_at: startedAt || undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: "grid", gap: 12 }}>
      {showTenantId && (
        <label>
          Tenant ID
          <input value={tenantId} onChange={(e) => setTenantId(e.target.value)} required />
        </label>
      )}
      {showClientId && (
        <label>
          Client ID
          <input value={clientId} onChange={(e) => setClientId(e.target.value)} required />
        </label>
      )}
      {showTariffPlanId && (
        <label>
          Tariff plan ID
          <input value={tariffPlanId} onChange={(e) => setTariffPlanId(e.target.value)} required />
        </label>
      )}
      <label>
        Billing day
        <input value={billingDay} onChange={(e) => setBillingDay(e.target.value)} />
      </label>
      <label>
        Started at
        <input type="date" value={startedAt} onChange={(e) => setStartedAt(e.target.value)} />
      </label>
      <button type="submit" disabled={submitting}>
        {submitting ? "Сохраняем..." : submitLabel}
      </button>
    </form>
  );
};
