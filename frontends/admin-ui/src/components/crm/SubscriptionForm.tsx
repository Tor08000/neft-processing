import React, { useEffect, useState } from "react";
import type { CrmSubscription } from "../../types/crm";

interface SubscriptionFormProps {
  initialValues?: Partial<CrmSubscription>;
  onSubmit: (values: Partial<CrmSubscription>) => void | Promise<void>;
  submitting?: boolean;
  submitLabel?: string;
}

export const SubscriptionForm: React.FC<SubscriptionFormProps> = ({
  initialValues,
  onSubmit,
  submitting,
  submitLabel = "Сохранить",
}) => {
  const [clientId, setClientId] = useState(initialValues?.client_id ?? "");
  const [tariffId, setTariffId] = useState(initialValues?.tariff_id ?? "");
  const [billingDay, setBillingDay] = useState(String(initialValues?.billing_day ?? ""));
  const [startedAt, setStartedAt] = useState(initialValues?.started_at ?? "");

  useEffect(() => {
    setClientId(initialValues?.client_id ?? "");
    setTariffId(initialValues?.tariff_id ?? "");
    setBillingDay(String(initialValues?.billing_day ?? ""));
    setStartedAt(initialValues?.started_at ?? "");
  }, [initialValues]);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    onSubmit({
      client_id: clientId,
      tariff_id: tariffId,
      billing_day: billingDay ? Number(billingDay) : undefined,
      started_at: startedAt || undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: "grid", gap: 12 }}>
      <label>
        Client ID
        <input value={clientId} onChange={(e) => setClientId(e.target.value)} required />
      </label>
      <label>
        Tariff ID
        <input value={tariffId} onChange={(e) => setTariffId(e.target.value)} required />
      </label>
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
