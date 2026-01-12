import React from "react";
import { PayoutReconcileResult } from "../../types/payouts";
import { formatRub } from "../../utils/format";
import { CopyButton } from "../CopyButton/CopyButton";

interface ReconcilePanelProps {
  data: PayoutReconcileResult | null;
  onCopyDiagnostics?: () => void;
}

export const ReconcilePanel: React.FC<ReconcilePanelProps> = ({ data, onCopyDiagnostics }) => {
  if (!data) return null;
  const mismatch = data.status === "MISMATCH";

  return (
    <div className="neft-card">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <h3>Reconciliation</h3>
        <span className={`neft-chip ${mismatch ? "neft-chip-err" : "neft-chip-ok"}`}>{data.status}</span>
      </div>
      <table className="neft-table" style={{ marginTop: 12 }}>
        <thead>
          <tr>
            <th></th>
            <th>Total amount</th>
            <th>Operations count</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Computed</td>
            <td>{formatRub(data.computed.total_amount)}</td>
            <td>{data.computed.operations_count}</td>
          </tr>
          <tr>
            <td>Recorded</td>
            <td>{formatRub(data.recorded.total_amount)}</td>
            <td>{data.recorded.operations_count}</td>
          </tr>
          <tr style={{ color: mismatch ? "var(--neft-error)" : "inherit", fontWeight: 700 }}>
            <td>Diff</td>
            <td>{formatRub(data.diff.amount)}</td>
            <td>{data.diff.count}</td>
          </tr>
        </tbody>
      </table>
      {mismatch && (
        <div style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ color: "var(--neft-error)", fontWeight: 600 }}>Mismatch detected. Check diagnostics.</span>
          <CopyButton
            value={JSON.stringify(data, null, 2)}
            label="Copy diagnostics JSON"
            onCopy={onCopyDiagnostics}
          />
        </div>
      )}
    </div>
  );
};
