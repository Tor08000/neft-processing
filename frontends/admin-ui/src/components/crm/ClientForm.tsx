import React, { useEffect, useState } from "react";
import type { CrmClient } from "../../types/crm";

interface ClientFormProps {
  initialValues?: Partial<CrmClient>;
  onSubmit: (values: Partial<CrmClient>) => void | Promise<void>;
  submitting?: boolean;
  submitLabel?: string;
  showClientId?: boolean;
}

export const ClientForm: React.FC<ClientFormProps> = ({
  initialValues,
  onSubmit,
  submitting,
  submitLabel = "Сохранить",
  showClientId = true,
}) => {
  const [clientId, setClientId] = useState(initialValues?.client_id ?? "");
  const [legalName, setLegalName] = useState(initialValues?.legal_name ?? "");
  const [status, setStatus] = useState(initialValues?.status ?? "");
  const [country, setCountry] = useState(initialValues?.country ?? "");
  const [timezone, setTimezone] = useState(initialValues?.timezone ?? "");

  useEffect(() => {
    setClientId(initialValues?.client_id ?? "");
    setLegalName(initialValues?.legal_name ?? "");
    setStatus(initialValues?.status ?? "");
    setCountry(initialValues?.country ?? "");
    setTimezone(initialValues?.timezone ?? "");
  }, [initialValues]);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    onSubmit({
      client_id: clientId,
      legal_name: legalName,
      status: status || undefined,
      country: country || undefined,
      timezone: timezone || undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: "grid", gap: 12 }}>
      {showClientId && (
        <label>
          Client ID
          <input value={clientId} onChange={(e) => setClientId(e.target.value)} required />
        </label>
      )}
      <label>
        Legal name
        <input value={legalName} onChange={(e) => setLegalName(e.target.value)} required />
      </label>
      <label>
        Status
        <input value={status} onChange={(e) => setStatus(e.target.value)} placeholder="ACTIVE" />
      </label>
      <label>
        Country
        <input value={country} onChange={(e) => setCountry(e.target.value)} placeholder="RU" />
      </label>
      <label>
        Timezone
        <input value={timezone} onChange={(e) => setTimezone(e.target.value)} placeholder="Europe/Moscow" />
      </label>
      <button type="submit" disabled={submitting}>
        {submitting ? "Сохраняем..." : submitLabel}
      </button>
    </form>
  );
};
