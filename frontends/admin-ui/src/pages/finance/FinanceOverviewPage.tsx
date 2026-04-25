import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchFinanceOverview } from "../../api/finance";
import type { FinanceOverview } from "../../types/finance";
import { extractRequestId } from "../ops/opsUtils";
import { ApiError } from "../../api/http";
import { AdminMisconfigPage } from "../admin/AdminStatusPages";
import { EmptyState } from "../../components/common/EmptyState";
import { ErrorState } from "../../components/common/ErrorState";
import { Loader } from "../../components/Loader/Loader";
import { FinanceOverview as BrandFinanceOverview } from "@shared/brand/components";

export const FinanceOverviewPage: React.FC = () => {
  const [window, setWindow] = useState<"24h" | "7d">("24h");
  const [overview, setOverview] = useState<FinanceOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [retryKey, setRetryKey] = useState(0);

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
  }, [window, retryKey]);

  const requestId = error ? extractRequestId(error) : null;

  if (loading) {
    return (
      <div className="card">
        <Loader label="Loading finance overview..." />
      </div>
    );
  }

  if (error instanceof ApiError && error.status === 404) {
    return <AdminMisconfigPage requestId={error.requestId ?? undefined} errorId={error.errorCode ?? undefined} />;
  }

  if (!overview) {
    return (
      <ErrorState
        title="Finance overview unavailable"
        description={error?.message ?? "Overview did not return data for this environment."}
        requestId={requestId}
        actionLabel="Retry"
        onAction={() => setRetryKey((value) => value + 1)}
      />
    );
  }

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <div className="surface-toolbar">
        <div>
          <h1 className="neft-h1">Finance overview</h1>
        </div>
        <div className="toolbar-actions">
          <button type="button" className={window === "24h" ? "neft-btn" : "ghost"} onClick={() => setWindow("24h")}>
            24h
          </button>
          <button type="button" className={window === "7d" ? "neft-btn" : "ghost"} onClick={() => setWindow("7d")}>
            7d
          </button>
        </div>
      </div>

      {error ? (
        <ErrorState
          title="Finance overview may be stale"
          description={error.message}
          requestId={requestId}
          actionLabel="Retry"
          onAction={() => setRetryKey((value) => value + 1)}
        />
      ) : null}

      <BrandFinanceOverview
        items={[
          {
            id: "overdue-orgs",
            label: "Overdue orgs",
            value: overview.overdue_orgs,
            meta: `Amount: ${overview.overdue_amount}`,
            tone: "warning",
          },
          {
            id: "invoices-issued",
            label: "Invoices issued",
            value: overview.invoices_issued_24h,
            meta: `Paid: ${overview.invoices_paid_24h}`,
            tone: "info",
          },
          {
            id: "payment-intakes",
            label: "Payment intakes pending",
            value: overview.payment_intakes_pending,
          },
          {
            id: "reconciliation",
            label: "Reconciliation unmatched",
            value: overview.reconciliation_unmatched_24h,
            tone: "danger",
          },
          {
            id: "payout-queue",
            label: "Payout queue pending",
            value: overview.payout_queue_pending,
          },
          {
            id: "mor-violations",
            label: "MoR immutable violations",
            value: overview.mor_immutable_violations_24h,
            meta: `Clawback required: ${overview.clawback_required_24h}`,
            tone: "premium",
          },
        ]}
      />

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
          <EmptyState
            title="No blockers detected"
            description="Blocked payout reasons will appear here when the queue records a real blocker."
            actionLabel="Refresh"
            actionOnClick={() => setRetryKey((value) => value + 1)}
          />
        )}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Quick links</h3>
        <div className="toolbar-actions">
          <Link className="ghost" to="/finance/invoices">
            Invoices
          </Link>
          <Link className="ghost" to="/finance/payment-intakes">
            Payment intakes
          </Link>
          <Link className="ghost" to="/finance/reconciliation/imports">
            Reconciliation imports
          </Link>
          <Link className="ghost" to="/finance/payouts">
            Payout queue
          </Link>
        </div>
      </div>
    </div>
  );
};

export default FinanceOverviewPage;
