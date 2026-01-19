import React, { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  applyImportTransaction,
  getImport,
  ignoreImportTransaction,
  listImportTransactions,
  matchImport,
  parseImport,
} from "../../api/reconciliation";
import type { ReconciliationTransaction } from "../../types/reconciliationImports";
import AdminWriteActionModal from "../../components/admin/AdminWriteActionModal";
import { Loader } from "../../components/Loader/Loader";
import { useToast } from "../../components/Toast/useToast";
import { Toast } from "../../components/Toast/Toast";
import { extractRequestId } from "../ops/opsUtils";

type ActionState =
  | { type: "parse" | "match"; transaction?: undefined }
  | { type: "apply" | "ignore"; transaction: ReconciliationTransaction }
  | null;

export const ReconciliationImportDetailsPage: React.FC = () => {
  const { importId } = useParams();
  const { toast, showToast } = useToast();
  const [action, setAction] = useState<ActionState>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [invoiceIds, setInvoiceIds] = useState<Record<string, string>>({});

  const { data: importData, isLoading: importLoading, refetch: refetchImport } = useQuery({
    queryKey: ["reconciliation-import", importId],
    queryFn: () => getImport(importId || ""),
    enabled: Boolean(importId),
  });

  const { data: txData, isLoading: txLoading, refetch: refetchTx } = useQuery({
    queryKey: ["reconciliation-transactions", importId],
    queryFn: () => listImportTransactions({ import_id: importId }),
    enabled: Boolean(importId),
  });

  const transactions = txData?.items ?? [];
  const grouped = useMemo(() => {
    const map: Record<string, ReconciliationTransaction[]> = {};
    transactions.forEach((tx) => {
      const key = tx.matched_status || "UNKNOWN";
      if (!map[key]) map[key] = [];
      map[key].push(tx);
    });
    return map;
  }, [transactions]);

  const requestId = errorMessage ? extractRequestId(new Error(errorMessage)) : null;

  const handleConfirm = async ({ reason }: { reason: string }) => {
    if (!importId || !action) return;
    try {
      if (action.type === "parse") {
        await parseImport(importId, reason);
      } else if (action.type === "match") {
        await matchImport(importId, reason);
      } else if (action.type === "apply" && action.transaction) {
        const invoiceId = invoiceIds[action.transaction.id];
        if (!invoiceId) {
          showToast("error", "Enter invoice ID before applying");
          return;
        }
        await applyImportTransaction(action.transaction.id, { invoice_id: invoiceId, reason });
      } else if (action.type === "ignore" && action.transaction) {
        await ignoreImportTransaction(action.transaction.id, reason);
      }
      setAction(null);
      setErrorMessage(null);
      showToast("success", "Action completed");
      await Promise.all([refetchImport(), refetchTx()]);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setErrorMessage(message);
      showToast("error", "Failed to apply action");
    }
  };

  if (importLoading) {
    return <Loader label="Loading import" />;
  }

  if (!importData) {
    return <div>Import not found.</div>;
  }

  return (
    <div className="stack">
      <div className="page-header">
        <h1>Import {importData.id}</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <button type="button" className="ghost" onClick={() => refetchImport()}>
            Refresh
          </button>
          <button type="button" className="ghost" onClick={() => setAction({ type: "parse" })}>
            Parse
          </button>
          <button type="button" className="ghost" onClick={() => setAction({ type: "match" })}>
            Match
          </button>
        </div>
      </div>

      {errorMessage ? (
        <div style={{ color: "#dc2626" }}>
          {errorMessage}
          {requestId ? <div style={{ marginTop: 4 }}>Request ID: {requestId}</div> : null}
        </div>
      ) : null}

      <div className="card">
        <div>Status: {importData.status}</div>
        <div>Format: {importData.format}</div>
        <div>
          Period: {importData.period_from ?? "—"} → {importData.period_to ?? "—"}
        </div>
        <div>Uploaded: {importData.uploaded_at}</div>
        {importData.error ? <div style={{ color: "#dc2626" }}>Error: {importData.error}</div> : null}
      </div>

      {txLoading ? <Loader label="Loading transactions" /> : null}

      {Object.entries(grouped).map(([status, items]) => (
        <div key={status} className="card">
          <h3 style={{ marginTop: 0 }}>{status}</h3>
          {items.length === 0 ? (
            <div className="muted">No transactions.</div>
          ) : (
            <div style={{ display: "grid", gap: 12 }}>
              {items.map((tx) => (
                <div key={tx.id} className="card" style={{ border: "1px solid #e2e8f0" }}>
                  <div>
                    {tx.posted_at} · {tx.amount} {tx.currency}
                  </div>
                  <div className="muted">{tx.purpose_text ?? "—"}</div>
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
                    <input
                      placeholder="invoice_id"
                      value={invoiceIds[tx.id] ?? ""}
                      onChange={(event) =>
                        setInvoiceIds((prev) => ({
                          ...prev,
                          [tx.id]: event.target.value,
                        }))
                      }
                      style={{ minWidth: 220 }}
                    />
                    <button type="button" className="ghost" onClick={() => setAction({ type: "apply", transaction: tx })}>
                      Apply
                    </button>
                    <button type="button" className="ghost" onClick={() => setAction({ type: "ignore", transaction: tx })}>
                      Ignore
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}

      <AdminWriteActionModal
        isOpen={action !== null}
        title="Confirm reconciliation action"
        requirePhrase
        confirmPhrase="CONFIRM"
        onConfirm={handleConfirm}
        onCancel={() => setAction(null)}
      />

      <Toast message={toast.message} type={toast.type} visible={toast.visible} onDismiss={toast.onDismiss} />
    </div>
  );
};

export default ReconciliationImportDetailsPage;
