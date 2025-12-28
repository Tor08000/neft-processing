import React, { useState } from "react";
import { moneyReplay } from "../../api/moneyFlow";
import { useAuth } from "../../auth/AuthContext";
import { DataTable, type DataColumn } from "../../components/common/DataTable";
import { JsonViewer } from "../../components/common/JsonViewer";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import type { MoneyReplayResponse } from "../../types/money";
import { formatError } from "../../utils/apiErrors";

export const MoneyReplayPage: React.FC = () => {
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [clientId, setClientId] = useState("");
  const [periodId, setPeriodId] = useState("");
  const [scope, setScope] = useState<"SUBSCRIPTIONS" | "FUEL" | "ALL">("SUBSCRIPTIONS");
  const [mode, setMode] = useState<"DRY_RUN" | "COMPARE" | "REBUILD_LINKS">("DRY_RUN");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<MoneyReplayResponse | null>(null);

  const mismatches = Array.isArray(result?.mismatches) ? (result?.mismatches as Record<string, unknown>[]) : [];
  const columns: DataColumn<Record<string, unknown>>[] = mismatches.length
    ? Object.keys(mismatches[0]).map((key) => ({ key, title: key }))
    : [];

  const handleRun = async () => {
    if (!accessToken) return;
    setLoading(true);
    try {
      const response = await moneyReplay(accessToken, {
        client_id: clientId,
        billing_period_id: periodId,
        scope,
        mode,
      });
      setResult(response);
      showToast("success", "Replay completed");
    } catch (error: unknown) {
      showToast("error", formatError(error));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Toast toast={toast} />
      <h1>Money Replay</h1>
      <div style={{ display: "grid", gap: 12, marginBottom: 16 }}>
        <label>
          Client ID
          <input value={clientId} onChange={(event) => setClientId(event.target.value)} required />
        </label>
        <label>
          Billing period ID
          <input value={periodId} onChange={(event) => setPeriodId(event.target.value)} required />
        </label>
        <label>
          Scope
          <select value={scope} onChange={(event) => setScope(event.target.value as typeof scope)}>
            <option value="SUBSCRIPTIONS">SUBSCRIPTIONS</option>
            <option value="FUEL">FUEL</option>
            <option value="ALL">ALL</option>
          </select>
        </label>
        <label>
          Mode
          <select value={mode} onChange={(event) => setMode(event.target.value as typeof mode)}>
            <option value="DRY_RUN">DRY_RUN</option>
            <option value="COMPARE">COMPARE</option>
            <option value="REBUILD_LINKS">REBUILD_LINKS</option>
          </select>
        </label>
        <button type="button" onClick={handleRun} disabled={loading}>
          {loading ? "Running..." : "Run replay"}
        </button>
      </div>

      {result && (
        <div style={{ display: "grid", gap: 16 }}>
          <div>
            <h3>Diff summary</h3>
            <JsonViewer value={result.summary ?? {}} />
          </div>
          <div>
            <h3>Mismatches</h3>
            <DataTable data={mismatches} columns={columns} emptyMessage="No mismatches" />
          </div>
          <div>
            <h3>Recommended actions</h3>
            <div>{result.recommended_actions ?? "-"}</div>
          </div>
          <details>
            <summary>Raw JSON</summary>
            <JsonViewer value={result} />
          </details>
        </div>
      )}
    </div>
  );
};

export default MoneyReplayPage;
