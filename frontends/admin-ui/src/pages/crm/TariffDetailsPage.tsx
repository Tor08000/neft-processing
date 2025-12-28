import React, { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { listTariffs, updateTariff } from "../../api/crm";
import { useAuth } from "../../auth/AuthContext";
import { JsonViewer } from "../../components/common/JsonViewer";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import type { CrmTariff } from "../../types/crm";
import { formatError } from "../../utils/apiErrors";

export const TariffDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [tariff, setTariff] = useState<CrmTariff | null>(null);
  const [jsonText, setJsonText] = useState("{}");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!accessToken || !id) return;
    listTariffs(accessToken, { tariff_id: id })
      .then((response) => {
        const found = response.items.find((item) => item.tariff_id === id || item.id === id) ?? null;
        setTariff(found);
        if (found?.definition) {
          setJsonText(JSON.stringify(found.definition, null, 2));
        }
      })
      .catch((error: unknown) => showToast("error", formatError(error)));
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

  if (!tariff) {
    return (
      <div>
        <Toast toast={toast} />
        <h1>Tariff not found</h1>
      </div>
    );
  }

  return (
    <div>
      <Toast toast={toast} />
      <h1>Tariff {tariff.tariff_id ?? tariff.id}</h1>
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
        {validationError && <div style={{ color: "#dc2626" }}>{validationError}</div>}
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
