import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getTariff, updateTariff } from "../../api/crm";
import { useAuth } from "../../auth/AuthContext";
import { EmptyState } from "../../components/common/EmptyState";
import { ErrorState } from "../../components/common/ErrorState";
import { JsonViewer } from "../../components/common/JsonViewer";
import { Loader } from "../../components/Loader/Loader";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import type { CrmTariff } from "../../types/crm";
import { describeError, formatError } from "../../utils/apiErrors";

export const TariffDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [tariff, setTariff] = useState<CrmTariff | null>(null);
  const [jsonText, setJsonText] = useState("{}");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadErrorDetails, setLoadErrorDetails] = useState<string | undefined>(undefined);

  useEffect(() => {
    if (!accessToken || !id) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setLoadError(null);
    setLoadErrorDetails(undefined);
    setTariff(null);
    getTariff(accessToken, id)
      .then((response) => {
        setTariff(response);
        if (response?.definition) {
          setJsonText(JSON.stringify(response.definition, null, 2));
        }
      })
      .catch((error: unknown) => {
        const summary = describeError(error);
        setLoadError(summary.message);
        setLoadErrorDetails(summary.details);
        showToast("error", formatError(error));
      })
      .finally(() => setLoading(false));
  }, [accessToken, id, showToast]);

  const parsedDefinition = useMemo(() => {
    try {
      return JSON.parse(jsonText);
    } catch {
      return null;
    }
  }, [jsonText]);

  const handleValidate = () => {
    try {
      JSON.parse(jsonText);
      setValidationError(null);
      showToast("success", "JSON valid");
    } catch (error: unknown) {
      setValidationError((error as Error).message);
    }
  };

  const handleSave = async () => {
    if (!accessToken || !id) return;
    try {
      const parsed = JSON.parse(jsonText);
      setSaving(true);
      const updated = await updateTariff(accessToken, id, { definition: parsed });
      setTariff(updated);
      showToast("success", "Tariff updated");
    } catch (error: unknown) {
      showToast("error", formatError(error));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <Loader label="Loading tariff detail" />;
  }

  if (!id) {
    return (
      <EmptyState
        title="Tariff ID is required"
        description="Open the tariff detail page from the CRM tariffs list."
        primaryAction={{ label: "Back to tariffs", onClick: () => navigate("/crm/tariffs") }}
      />
    );
  }

  if (loadError) {
    return (
      <ErrorState
        title="Failed to load tariff detail"
        description={loadError}
        details={loadErrorDetails}
        actionLabel="Back to tariffs"
        onAction={() => navigate("/crm/tariffs")}
      />
    );
  }

  if (!tariff) {
    return (
      <EmptyState
        title="Tariff not found"
        description="The requested tariff is missing or no longer available."
        primaryAction={{ label: "Back to tariffs", onClick: () => navigate("/crm/tariffs") }}
      />
    );
  }

  return (
    <div>
      <Toast toast={toast} />
      <h1>Tariff {tariff.tariff_id ?? tariff.id}</h1>
      <div style={{ marginBottom: 16, display: "grid", gap: 6 }}>
        <div>Status: {tariff.status}</div>
        <div>Billing period: {tariff.billing_period}</div>
        <div>Base fee minor: {tariff.base_fee_minor}</div>
        <div>Currency: {tariff.currency}</div>
      </div>
      <div style={{ marginBottom: 16 }}>
        <JsonViewer value={tariff.definition ?? {}} title="Definition JSON" />
      </div>
      <div style={{ display: "grid", gap: 8 }}>
        <label>
          Raw JSON
          <textarea
            value={jsonText}
            onChange={(event) => setJsonText(event.target.value)}
            rows={16}
            style={{ width: "100%", fontFamily: "monospace" }}
          />
        </label>
        {validationError ? <div style={{ color: "#dc2626" }}>{validationError}</div> : null}
        <div style={{ display: "flex", gap: 8 }}>
          <button type="button" onClick={handleValidate}>
            Validate
          </button>
          <button type="button" onClick={handleSave} disabled={!parsedDefinition || saving}>
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
};

export default TariffDetailsPage;
