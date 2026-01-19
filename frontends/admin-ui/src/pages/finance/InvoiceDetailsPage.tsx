import React, { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchFinanceInvoice, markInvoicePaid, voidInvoice, markInvoiceOverdue } from "../../api/finance";
import AdminWriteActionModal from "../../components/admin/AdminWriteActionModal";
import { Loader } from "../../components/Loader/Loader";
import { useToast } from "../../components/Toast/useToast";
import { Toast } from "../../components/Toast/Toast";
import { extractRequestId } from "../ops/opsUtils";

type ActionType = "mark-paid" | "void" | "mark-overdue" | null;

export const InvoiceDetailsPage: React.FC = () => {
  const { invoiceId } = useParams();
  const { toast, showToast } = useToast();
  const [action, setAction] = useState<ActionType>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["finance-invoice", invoiceId],
    queryFn: () => fetchFinanceInvoice(invoiceId || ""),
    enabled: Boolean(invoiceId),
  });

  const requestId = useMemo(() => (errorMessage ? extractRequestId(new Error(errorMessage)) : null), [errorMessage]);

  const handleConfirm = async ({ reason }: { reason: string }) => {
    if (!invoiceId) return;
    try {
      if (action === "mark-paid") {
        await markInvoicePaid(invoiceId, reason);
      } else if (action === "void") {
        await voidInvoice(invoiceId, reason);
      } else if (action === "mark-overdue") {
        await markInvoiceOverdue(invoiceId, reason);
      }
      setAction(null);
      setErrorMessage(null);
      showToast("success", "Action completed");
      await refetch();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setErrorMessage(message);
      showToast("error", "Failed to apply action");
    }
  };

  if (isLoading) {
    return <Loader label="Loading invoice" />;
  }

  if (!data) {
    return <div>Invoice not found.</div>;
  }

  return (
    <div className="stack">
      <div className="page-header">
        <h1>Invoice {data.id}</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <button type="button" className="ghost" onClick={() => refetch()}>
            Refresh
          </button>
          {data.pdf_url ? (
            <a className="ghost" href={data.pdf_url} target="_blank" rel="noreferrer">
              Download PDF
            </a>
          ) : null}
        </div>
      </div>

      {errorMessage ? (
        <div style={{ color: "#dc2626" }}>
          {errorMessage}
          {requestId ? <div style={{ marginTop: 4 }}>Request ID: {requestId}</div> : null}
        </div>
      ) : null}

      <div className="card">
        <div>Status: {data.status}</div>
        <div>Org: {data.org_id ?? "—"}</div>
        <div>Subscription: {data.subscription_id ?? "—"}</div>
        <div>
          Period: {data.period_start ?? "—"} → {data.period_end ?? "—"}
        </div>
        <div>Due at: {data.due_at ?? "—"}</div>
        <div>Paid at: {data.paid_at ?? "—"}</div>
        <div>
          Total: {data.total ?? "—"} {data.currency ?? ""}
        </div>
      </div>

      <div className="card" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button type="button" className="neft-btn" onClick={() => setAction("mark-paid")}>
          Mark paid
        </button>
        <button type="button" className="neft-btn-secondary" onClick={() => setAction("mark-overdue")}>
          Mark overdue
        </button>
        <button type="button" className="ghost" onClick={() => setAction("void")}>
          Void
        </button>
      </div>

      <AdminWriteActionModal
        isOpen={action !== null}
        title="Confirm invoice action"
        requirePhrase
        confirmPhrase="CONFIRM"
        onConfirm={handleConfirm}
        onCancel={() => setAction(null)}
      />

      <Toast message={toast.message} type={toast.type} visible={toast.visible} onDismiss={toast.onDismiss} />
    </div>
  );
};

export default InvoiceDetailsPage;
