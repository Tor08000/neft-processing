import React, { useEffect, useState } from "react";
import type { CrmTariff } from "../../types/crm";

interface TariffFormProps {
  initialValues?: Partial<CrmTariff>;
  onSubmit: (values: Partial<CrmTariff>) => void | Promise<void>;
  submitting?: boolean;
  submitLabel?: string;
}

const domainsList = ["fuel", "logistics", "docs", "risk"];

export const TariffForm: React.FC<TariffFormProps> = ({ initialValues, onSubmit, submitting, submitLabel = "Сохранить" }) => {
  const [name, setName] = useState(initialValues?.name ?? "");
  const [status, setStatus] = useState(initialValues?.status ?? "");
  const [baseFee, setBaseFee] = useState(String(initialValues?.base_fee ?? ""));
  const [includedSummary, setIncludedSummary] = useState(initialValues?.included_summary ?? "");
  const [domains, setDomains] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setName(initialValues?.name ?? "");
    setStatus(initialValues?.status ?? "");
    setBaseFee(String(initialValues?.base_fee ?? ""));
    setIncludedSummary(initialValues?.included_summary ?? "");
    setDomains(initialValues?.domains ?? {});
  }, [initialValues]);

  const toggleDomain = (key: string) => {
    setDomains((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    onSubmit({
      name,
      status: status || undefined,
      base_fee: baseFee ? Number(baseFee) : undefined,
      included_summary: includedSummary || undefined,
      domains,
    });
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: "grid", gap: 12 }}>
      <label>
        Tariff name
        <input value={name} onChange={(e) => setName(e.target.value)} required />
      </label>
      <label>
        Status
        <input value={status} onChange={(e) => setStatus(e.target.value)} placeholder="ACTIVE" />
      </label>
      <label>
        Base fee
        <input value={baseFee} onChange={(e) => setBaseFee(e.target.value)} />
      </label>
      <label>
        Included summary
        <input value={includedSummary} onChange={(e) => setIncludedSummary(e.target.value)} />
      </label>
      <div>
        <div style={{ fontWeight: 600, marginBottom: 6 }}>Domains</div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          {domainsList.map((domain) => (
            <label key={domain} style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <input type="checkbox" checked={Boolean(domains[domain])} onChange={() => toggleDomain(domain)} />
              {domain}
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
