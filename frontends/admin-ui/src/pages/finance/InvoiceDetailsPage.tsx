import React, { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchFinanceInvoice, markInvoicePaid, voidInvoice, markInvoiceOverdue } from "../../api/finance";
import AdminWriteActionModal from "../../components/admin/AdminWriteActionModal";
import { Loader } from "../../components/Loader/Loader";
import { useToast } from "../../components/Toast/useToast";
import { Toast } from "../../components/Toast/Toast";
import { EmptyState } from "../../components/common/EmptyState";
import { ErrorState } from "../../components/common/ErrorState";
import { extractRequestId } from "../ops/opsUtils";
import { useAdmin } from "../../admin/AdminContext";
import { FinanceOverview } from "@shared/brand/components";

type ActionType = "mark-paid" | "void" | "mark-overdue" | null;

export const InvoiceDetailsPage: React.FC = () => {
  const { invoiceId } = useParams();
  const { toast, showToast } = useToast();
  const { profile } = useAdmin();
  const [action, setAction] = useState<ActionType>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const canWrite = Boolean(profile?.permissions.finance?.write) && !profile?.read_only;

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["finance-invoice", invoiceId],
    queryFn: () => fetchFinanceInvoice(invoiceId || ""),
    enabled: Boolean(invoiceId),
  });

  const requestId = useMemo(() => (errorMessage ? extractRequestId(new Error(errorMessage)) : null), [errorMessage]);
  const loadRequestId = useMemo(() => (error ? extractRequestId(error) : null), [error]);

  const handleConfirm = async ({ reason, correlationId }: { reason: string; correlationId: string }) => {
    if (!invoiceId) return;
    if (!canWrite) return;
    try {
      if (action === "mark-paid") {
        await markInvoicePaid(invoiceId, { reason, correlation_id: correlationId });
      } else if (action === "void") {
        await voidInvoice(invoiceId, { reason, correlation_id: correlationId });
      } else if (action === "mark-overdue") {
        await markInvoiceOverdue(invoiceId, { reason, correlation_id: correlationId });
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

  if (!invoiceId) {
    return <EmptyState title="Invoice not found" description="Check the route and open the invoice again." />;
  }

  if (isLoading) {
    return <Loader label="Loading invoice" />;
  }

  if (error) {
    return (
      <ErrorState
        title="Failed to load invoice"
        description={(error as Error).message}
        requestId={loadRequestId}
        actionLabel="Retry"
        onAction={() => void refetch()}
      />
    );
  }

  if (!data) {
    return <EmptyState title="Invoice not found" description="The requested invoice is unavailable." />;
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
        <ErrorState title="Failed to apply invoice action" description={errorMessage} requestId={requestId} />
      ) : null}

      <FinanceOverview
        items={[
          {
            id: "status",
            label: "Status",
            value: data.status,
            meta: `Paid at: ${data.paid_at ?? "—"}`,
            tone: data.status === "OVERDUE" ? "warning" : "info",
          },
          {
            id: "total",
            label: "Total",
            value: `${data.total ?? "—"} ${data.currency ?? ""}`.trim(),
            meta: `Due at: ${data.due_at ?? "—"}`,
            tone: "premium",
          },
          {
            id: "org",
            label: "Org",
            value: data.org_id ?? "—",
          },
          {
            id: "subscription",
            label: "Subscription",
            value: data.subscription_id ?? "—",
          },
          {
            id: "period",
            label: "Period",
            value: `${data.period_start ?? "—"} → ${data.period_end ?? "—"}`,
          },
        ]}
      />

      <div className="card">
        <h3 style={{ marginTop: 0 }}>State explain</h3>
        {data.state_explain ? (
          <div style={{ display: "grid", gap: 6 }}>
            <div>Current status: {data.state_explain.current_status}</div>
            <div>PDF status: {data.state_explain.pdf_status ?? "—"}</div>
            <div>Has PDF: {data.state_explain.has_pdf ? "Yes" : "No"}</div>
            <div>Overdue: {data.state_explain.is_overdue ? "Yes" : "No"}</div>
            <div>Payment intakes: {data.state_explain.payment_intakes_total}</div>
            <div>Pending intakes: {data.state_explain.payment_intakes_pending}</div>
            <div>Latest intake status: {data.state_explain.latest_payment_intake_status ?? "—"}</div>
            <div>Reconciliation request: {data.state_explain.reconciliation_request_id ?? "—"}</div>
          </div>
        ) : (
          <EmptyState
            title="No state explain available"
            description="Owner explain data will appear after invoice lifecycle events are recorded."
          />
        )}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Timeline</h3>
        {data.timeline?.length ? (
          <ul style={{ paddingLeft: 18, marginBottom: 0 }}>
            {data.timeline.map((event) => (
              <li key={`${event.entity_type}-${event.entity_id}-${event.event_type}-${event.ts ?? "ts"}`}>
                {event.event_type}
                {event.ts ? ` · ${event.ts}` : ""}
                {event.reason ? ` · reason: ${event.reason}` : ""}
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState
            title="No owner timeline yet"
            description="Billing and reconciliation events will appear here after invoice actions."
          />
        )}
      </div>

      <div className="card" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button type="button" className="neft-btn" onClick={() => setAction("mark-paid")} disabled={!canWrite}>
          Mark paid
        </button>
        <button type="button" className="neft-btn-secondary" onClick={() => setAction("mark-overdue")} disabled={!canWrite}>
          Mark overdue
        </button>
        <button type="button" className="ghost" onClick={() => setAction("void")} disabled={!canWrite}>
          Void
        </button>
        {!canWrite ? <span className="muted">Read-only mode enabled</span> : null}
      </div>

      <AdminWriteActionModal
        isOpen={action !== null}
        title="Confirm invoice action"
        requirePhrase
        confirmPhrase="CONFIRM"
        onConfirm={handleConfirm}
        onCancel={() => setAction(null)}
      />

      <Toast toast={toast} />
    </div>
  );
};

export default InvoiceDetailsPage;
