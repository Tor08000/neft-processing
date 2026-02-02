import React, { useEffect, useState } from "react";
import { fetchFinanceOverview } from "../../api/finance";
import type { FinanceOverview } from "../../types/finance";
import { extractRequestId } from "../ops/opsUtils";
import { ApiError } from "../../api/http";
import { AdminMisconfigPage } from "../admin/AdminStatusPages";

const KPI_STYLE: React.CSSProperties = {
  display: "grid",
  gap: 16,
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
};

export const FinanceOverviewPage: React.FC = () => {
  const [window, setWindow] = useState<"24h" | "7d">("24h");
  const [overview, setOverview] = useState<FinanceOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    setLoading(true);
    fetchFinanceOverview(window)
      .then((data) => {
        setOverview(data);
        setError(null);
      })
      .catch((err: Error) => {
        setError(err);
      })
      .finally(() => setLoading(false));
  }, [window]);

  const requestId = error ? extractRequestId(error) : null;

  if (loading) {
    return <div>Loading finance overview…</div>;
  }

  if (error instanceof ApiError && error.status === 404) {
    return <AdminMisconfigPage requestId={error.requestId ?? undefined} errorId={error.errorCode ?? undefined} />;
  }

  if (!overview) {
    return (
      <div>
        <h1>Finance overview</h1>
        <div style={{ color: "#dc2626" }}>Failed to load overview: {error?.message ?? "Unknown error"}</div>
        {requestId ? <div style={{ marginTop: 8 }}>Request ID: {requestId}</div> : null}
      </div>
    );
  }

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <div>
        <h1 style={{ marginBottom: 8 }}>Finance overview</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <button type="button" className={window === "24h" ? "neft-btn" : "ghost"} onClick={() => setWindow("24h")}>
            24h
          </button>
          <button type="button" className={window === "7d" ? "neft-btn" : "ghost"} onClick={() => setWindow("7d")}>
            7d
          </button>
        </div>
      </div>

      {error ? (
        <div style={{ color: "#dc2626" }}>
          {error.message}
          {requestId ? <div style={{ marginTop: 4 }}>Request ID: {requestId}</div> : null}
        </div>
      ) : null}

      <div style={KPI_STYLE}>
        <div className="card">
          <div className="muted">Overdue orgs</div>
          <div style={{ fontSize: 22, fontWeight: 600 }}>{overview.overdue_orgs}</div>
          <div className="muted">Amount: {overview.overdue_amount}</div>
        </div>
        <div className="card">
          <div className="muted">Invoices issued</div>
          <div style={{ fontSize: 22, fontWeight: 600 }}>{overview.invoices_issued_24h}</div>
          <div className="muted">Paid: {overview.invoices_paid_24h}</div>
        </div>
        <div className="card">
          <div className="muted">Payment intakes pending</div>
          <div style={{ fontSize: 22, fontWeight: 600 }}>{overview.payment_intakes_pending}</div>
        </div>
        <div className="card">
          <div className="muted">Reconciliation unmatched</div>
          <div style={{ fontSize: 22, fontWeight: 600 }}>{overview.reconciliation_unmatched_24h}</div>
        </div>
        <div className="card">
          <div className="muted">Payout queue pending</div>
          <div style={{ fontSize: 22, fontWeight: 600 }}>{overview.payout_queue_pending}</div>
        </div>
        <div className="card">
          <div className="muted">MoR immutable violations</div>
          <div style={{ fontSize: 22, fontWeight: 600 }}>{overview.mor_immutable_violations_24h}</div>
          <div className="muted">Clawback required: {overview.clawback_required_24h}</div>
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Payout blockers (top 5)</h3>
        {overview.payout_blocked_top_reasons.length ? (
          <ul style={{ paddingLeft: 18, marginBottom: 0 }}>
            {overview.payout_blocked_top_reasons.map((item) => (
              <li key={item.reason}>
                {item.reason}: {item.count}
              </li>
            ))}
          </ul>
        ) : (
          <div className="muted">No blockers detected.</div>
        )}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Quick links</h3>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
          <a className="ghost" href="/finance/invoices">
            Invoices
          </a>
          <a className="ghost" href="/finance/payment-intakes">
            Payment intakes
          </a>
          <a className="ghost" href="/finance/reconciliation/imports">
            Reconciliation imports
          </a>
          <a className="ghost" href="/finance/payouts">
            Payout queue
          </a>
        </div>
      </div>
    </div>
  );
};

export default FinanceOverviewPage;
