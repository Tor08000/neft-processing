import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { approvePaymentIntake, listPaymentIntakes, rejectPaymentIntake } from "../../api/billing";
import { Table, type Column } from "../../components/Table/Table";
import { formatDateTime } from "../../utils/format";
import type { BillingPaymentIntake, BillingPaymentIntakeStatus } from "../../types/paymentIntakes";
import { formatMoney } from "./billingUtils";

const STATUS_OPTIONS: BillingPaymentIntakeStatus[] = ["SUBMITTED", "UNDER_REVIEW", "APPROVED", "REJECTED"];

const BillingPaymentIntakesPage: React.FC = () => {
  const [items, setItems] = useState<BillingPaymentIntake[]>([]);
  const [status, setStatus] = useState<BillingPaymentIntakeStatus | "">("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setIsLoading(true);
    setError(null);
    listPaymentIntakes({ status: status || undefined })
      .then((response) => {
        setItems(response.items ?? []);
      })
      .catch((err: unknown) => setError((err as Error).message))
      .finally(() => setIsLoading(false));
  }, [status]);

  useEffect(() => {
    load();
  }, [load]);

  const handleApprove = useCallback(
    async (intake: BillingPaymentIntake) => {
      await approvePaymentIntake(intake.id);
      load();
    },
    [load],
  );

  const handleReject = useCallback(
    async (intake: BillingPaymentIntake) => {
      const reason = window.prompt("Причина отклонения");
      if (!reason) return;
      await rejectPaymentIntake(intake.id, { review_note: reason });
      load();
    },
    [load],
  );

  const columns = useMemo<Column<BillingPaymentIntake>[]>(
    () => [
      {
        key: "invoice",
        title: "Invoice ID",
        render: (item) => (
          <Link className="ghost" to={`/billing/invoices/${item.invoice_id}`}>
            {item.invoice_id}
          </Link>
        ),
      },
      {
        key: "org",
        title: "Org",
        render: (item) => String(item.org_id),
      },
      {
        key: "amount",
        title: "Amount",
        render: (item) => formatMoney(item.amount, item.currency),
      },
      {
        key: "status",
        title: "Status",
        render: (item) => item.status,
      },
      {
        key: "submitted_at",
        title: "Submitted at",
        render: (item) => formatDateTime(item.created_at),
      },
      {
        key: "proof",
        title: "Proof",
        render: (item) =>
          item.proof_url ? (
            <a className="ghost" href={item.proof_url} target="_blank" rel="noreferrer">
              Download
            </a>
          ) : (
            "—"
          ),
      },
      {
        key: "actions",
        title: "Actions",
        render: (item) => (
          <div className="stack-inline" style={{ gap: 8 }}>
            <button type="button" className="ghost" onClick={() => handleApprove(item)} disabled={item.status === "APPROVED"}>
              Approve
            </button>
            <button type="button" className="ghost" onClick={() => handleReject(item)} disabled={item.status === "REJECTED"}>
              Reject
            </button>
          </div>
        ),
      },
    ],
    [handleApprove, handleReject],
  );

  return (
    <div className="stack">
      <section className="card">
        <div className="card__header" style={{ justifyContent: "space-between", gap: 16 }}>
          <div>
            <h2 style={{ marginTop: 0 }}>Payment intakes</h2>
            <p className="muted">Manual bank transfer confirmations from clients.</p>
          </div>
          <label className="filter">
            Status
            <select value={status} onChange={(event) => setStatus(event.target.value as BillingPaymentIntakeStatus | "")}>
              <option value="">All</option>
              {STATUS_OPTIONS.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      {error ? <div className="card error-state">{error}</div> : null}

      <Table
        columns={columns}
        data={items}
        loading={isLoading}
        emptyState={{ title: "No payment intakes", description: "Client-submitted confirmations appear here." }}
      />
    </div>
  );
};

export default BillingPaymentIntakesPage;
