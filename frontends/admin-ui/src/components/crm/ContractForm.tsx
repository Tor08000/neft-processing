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

export const ContractForm: React.FC<ContractFormProps> = ({
  initialValues,
  onSubmit,
  submitting,
  submitLabel = "Сохранить",
  showClientId = true,
  limitProfiles = [],
  riskProfiles = [],
}) => {
  const [contractNumber, setContractNumber] = useState(initialValues?.contract_number ?? "");
  const [clientId, setClientId] = useState(initialValues?.client_id ?? "");
  const [status, setStatus] = useState(initialValues?.status ?? "");
  const [validFrom, setValidFrom] = useState(initialValues?.valid_from ?? "");
  const [validTo, setValidTo] = useState(initialValues?.valid_to ?? "");
  const [tariffPlanId, setTariffPlanId] = useState(initialValues?.tariff_plan_id ?? "");
  const [limitProfile, setLimitProfile] = useState(initialValues?.limit_profile_id ?? "");
  const [riskProfile, setRiskProfile] = useState(initialValues?.risk_profile_id ?? "");
  const [documentsRequired, setDocumentsRequired] = useState(Boolean(initialValues?.documents_required));

  useEffect(() => {
    setContractNumber(initialValues?.contract_number ?? "");
    setClientId(initialValues?.client_id ?? "");
    setStatus(initialValues?.status ?? "");
    setValidFrom(initialValues?.valid_from ?? "");
    setValidTo(initialValues?.valid_to ?? "");
    setTariffPlanId(initialValues?.tariff_plan_id ?? "");
    setLimitProfile(initialValues?.limit_profile_id ?? "");
    setRiskProfile(initialValues?.risk_profile_id ?? "");
    setDocumentsRequired(Boolean(initialValues?.documents_required));
  }, [initialValues]);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    onSubmit({
      contract_number: contractNumber,
      client_id: clientId || undefined,
      status: status || undefined,
      valid_from: validFrom || undefined,
      valid_to: validTo || undefined,
      tariff_plan_id: tariffPlanId || undefined,
      limit_profile_id: limitProfile || undefined,
      risk_profile_id: riskProfile || undefined,
      documents_required: documentsRequired,
    });
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: "grid", gap: 12 }}>
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
        Tariff plan ID
        <input value={tariffPlanId} onChange={(e) => setTariffPlanId(e.target.value)} />
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
