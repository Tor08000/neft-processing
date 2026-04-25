import React, { useEffect, useState } from "react";
import type { CrmTariff } from "../../types/crm";

interface TariffFormProps {
  initialValues?: Partial<CrmTariff>;
  onSubmit: (values: Partial<CrmTariff>) => void | Promise<void>;
  submitting?: boolean;
  submitLabel?: string;
}

const featureKeys = [
  { key: "fuel", label: "fuel" },
  { key: "logistics", label: "logistics" },
  { key: "docs", label: "docs" },
  { key: "risk", label: "risk" },
  { key: "export", label: "export" },
  { key: "subscription_meter_fuel_enabled", label: "subscription_meter_fuel_enabled" },
];

export const TariffForm: React.FC<TariffFormProps> = ({ initialValues, onSubmit, submitting, submitLabel = "Сохранить" }) => {
  const [tariffId, setTariffId] = useState(initialValues?.tariff_id ?? initialValues?.id ?? "");
  const [name, setName] = useState(initialValues?.name ?? "");
  const [description, setDescription] = useState(initialValues?.description ?? "");
  const [status, setStatus] = useState(initialValues?.status ?? "");
  const [billingPeriod, setBillingPeriod] = useState(initialValues?.billing_period ?? "MONTHLY");
  const [baseFeeMinor, setBaseFeeMinor] = useState(String(initialValues?.base_fee_minor ?? ""));
  const [currency, setCurrency] = useState(initialValues?.currency ?? "RUB");
  const [features, setFeatures] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setTariffId(initialValues?.tariff_id ?? initialValues?.id ?? "");
    setName(initialValues?.name ?? "");
    setDescription(initialValues?.description ?? "");
    setStatus(initialValues?.status ?? "");
    setBillingPeriod(initialValues?.billing_period ?? "MONTHLY");
    setBaseFeeMinor(String(initialValues?.base_fee_minor ?? ""));
    setCurrency(initialValues?.currency ?? "RUB");
    setFeatures(initialValues?.features ?? {});
  }, [initialValues]);

  const toggleFeature = (key: string) => {
    setFeatures((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    onSubmit({
      id: tariffId,
      name,
      description: description || undefined,
      status: status || undefined,
      billing_period: billingPeriod,
      base_fee_minor: baseFeeMinor ? Number(baseFeeMinor) : undefined,
      currency,
      features,
    });
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: "grid", gap: 12 }}>
      <label>
        Tariff ID
        <input value={tariffId} onChange={(e) => setTariffId(e.target.value)} required />
      </label>
      <label>
        Tariff name
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label>
        Description
        <input value={description} onChange={(e) => setDescription(e.target.value)} />
      </label>
      <label>
        Status
        <input value={status} onChange={(e) => setStatus(e.target.value)} placeholder="ACTIVE" />
      </label>
      <label>
        Billing period
        <select value={billingPeriod} onChange={(e) => setBillingPeriod(e.target.value)}>
          <option value="MONTHLY">MONTHLY</option>
          <option value="YEARLY">YEARLY</option>
        </select>
      </label>
      <label>
        Base fee minor
        <input value={baseFeeMinor} onChange={(e) => setBaseFeeMinor(e.target.value)} />
      </label>
      <label>
        Currency
        <input value={currency} onChange={(e) => setCurrency(e.target.value)} placeholder="RUB" />
      </label>
      <div>
        <div style={{ fontWeight: 600, marginBottom: 6 }}>Features</div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          {featureKeys.map((feature) => (
            <label key={feature.key} style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <input
                type="checkbox"
                checked={Boolean(features[feature.key])}
                onChange={() => toggleFeature(feature.key)}
              />
              {feature.label}
            </label>
          ))}
        </div>
      </div>
      <button type="submit" disabled={submitting}>
        {submitting ? "Сохраняем..." : submitLabel}
      </button>
    </form>
  );
};
