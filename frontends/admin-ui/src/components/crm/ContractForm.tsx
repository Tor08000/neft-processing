import React, { useEffect, useState } from "react";
import type { CrmContract } from "../../types/crm";
import { LimitProfilePicker } from "./LimitProfilePicker";
import { RiskProfilePicker } from "./RiskProfilePicker";

interface ContractFormProps {
  initialValues?: Partial<CrmContract>;
  onSubmit: (values: Partial<CrmContract>) => void | Promise<void>;
  submitting?: boolean;
  submitLabel?: string;
  showClientId?: boolean;
  limitProfiles?: { id: string; name?: string | null }[];
  riskProfiles?: { id: string; name?: string | null }[];
}

const toDateInput = (value?: string | null) => (value ? value.slice(0, 10) : "");

export const ContractForm: React.FC<ContractFormProps> = ({
  initialValues,
  onSubmit,
  submitting,
  submitLabel = "Сохранить",
  showClientId = true,
  limitProfiles = [],
  riskProfiles = [],
}) => {
  const [tenantId, setTenantId] = useState(String(initialValues?.tenant_id ?? ""));
  const [contractNumber, setContractNumber] = useState(initialValues?.contract_number ?? "");
  const [clientId, setClientId] = useState(initialValues?.client_id ?? "");
  const [status, setStatus] = useState(initialValues?.status ?? "");
  const [validFrom, setValidFrom] = useState(toDateInput(initialValues?.valid_from));
  const [validTo, setValidTo] = useState(toDateInput(initialValues?.valid_to));
  const [billingMode, setBillingMode] = useState(initialValues?.billing_mode ?? "POSTPAID");
  const [currency, setCurrency] = useState(initialValues?.currency ?? "RUB");
  const [limitProfile, setLimitProfile] = useState(initialValues?.limit_profile_id ?? "");
  const [riskProfile, setRiskProfile] = useState(initialValues?.risk_profile_id ?? "");
  const [documentsRequired, setDocumentsRequired] = useState(Boolean(initialValues?.documents_required));

  useEffect(() => {
    setTenantId(String(initialValues?.tenant_id ?? ""));
    setContractNumber(initialValues?.contract_number ?? "");
    setClientId(initialValues?.client_id ?? "");
    setStatus(initialValues?.status ?? "");
    setValidFrom(toDateInput(initialValues?.valid_from));
    setValidTo(toDateInput(initialValues?.valid_to));
    setBillingMode(initialValues?.billing_mode ?? "POSTPAID");
    setCurrency(initialValues?.currency ?? "RUB");
    setLimitProfile(initialValues?.limit_profile_id ?? "");
    setRiskProfile(initialValues?.risk_profile_id ?? "");
    setDocumentsRequired(Boolean(initialValues?.documents_required));
  }, [initialValues]);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    onSubmit({
      tenant_id: tenantId ? Number(tenantId) : undefined,
      contract_number: contractNumber,
      client_id: clientId || undefined,
      status: status || undefined,
      valid_from: validFrom || undefined,
      valid_to: validTo || undefined,
      billing_mode: billingMode || undefined,
      currency: currency || undefined,
      limit_profile_id: limitProfile || undefined,
      risk_profile_id: riskProfile || undefined,
      documents_required: documentsRequired,
    });
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: "grid", gap: 12 }}>
      <label>
        Tenant ID
        <input value={tenantId} onChange={(e) => setTenantId(e.target.value)} required />
      </label>
      <label>
        Contract number
        <input value={contractNumber} onChange={(e) => setContractNumber(e.target.value)} required />
      </label>
      {showClientId && (
        <label>
          Client ID
          <input value={clientId} onChange={(e) => setClientId(e.target.value)} required />
        </label>
      )}
      <label>
        Status
        <input value={status} onChange={(e) => setStatus(e.target.value)} placeholder="ACTIVE" />
      </label>
      <label>
        Valid from
        <input type="date" value={validFrom} onChange={(e) => setValidFrom(e.target.value)} />
      </label>
      <label>
        Valid to
        <input type="date" value={validTo} onChange={(e) => setValidTo(e.target.value)} />
      </label>
      <label>
        Billing mode
        <select value={billingMode} onChange={(e) => setBillingMode(e.target.value)}>
          <option value="POSTPAID">POSTPAID</option>
          <option value="PREPAID">PREPAID</option>
        </select>
      </label>
      <label>
        Currency
        <input value={currency} onChange={(e) => setCurrency(e.target.value)} placeholder="RUB" />
      </label>
      <LimitProfilePicker profiles={limitProfiles} value={limitProfile} onChange={setLimitProfile} />
      <RiskProfilePicker profiles={riskProfiles} value={riskProfile} onChange={setRiskProfile} />
      <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <input type="checkbox" checked={documentsRequired} onChange={(e) => setDocumentsRequired(e.target.checked)} />
        Documents required
      </label>
      <button type="submit" disabled={submitting}>
        {submitting ? "Сохраняем..." : submitLabel}
      </button>
    </form>
  );
};
