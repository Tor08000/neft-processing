import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getPayment, listRefunds, refundPayment } from "../../api/billing";
import { UnauthorizedError } from "../../api/client";
import { CopyButton } from "../../components/CopyButton/CopyButton";
import { Table, type Column } from "../../components/Table/Table";
import { Toast } from "../../components/common/Toast";
import { JsonViewer } from "../../components/common/JsonViewer";
import { useToast } from "../../components/Toast/useToast";
import { formatDateTime } from "../../utils/format";
import { createIdempotencyKey } from "../../utils/uuid";
import type { BillingPayment, BillingRefund } from "../../types/billingFlows";
import { formatMoney, paymentStatusBadge, refundStatusBadge, renderBadge } from "./billingUtils";

const BillingPaymentDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { toast, showToast } = useToast();
  const [payment, setPayment] = useState<BillingPayment | null>(null);
  const [refunds, setRefunds] = useState<BillingRefund[]>([]);
  const [loading, setLoading] = useState(true);
  const [refundsLoading, setRefundsLoading] = useState(true);
  const [notAvailable, setNotAvailable] = useState(false);
  const [refundsUnavailable, setRefundsUnavailable] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [unauthorized, setUnauthorized] = useState(false);

  const [refundModalOpen, setRefundModalOpen] = useState(false);
  const [refundAmount, setRefundAmount] = useState("");
  const [refundProviderId, setRefundProviderId] = useState("");
  const [refundIdempotencyKey, setRefundIdempotencyKey] = useState("");
  const [refundError, setRefundError] = useState<string | null>(null);
  const [refundErrorDetail, setRefundErrorDetail] = useState<string | null>(null);

  const loadPayment = useCallback(() => {
    if (!id) return;
    setLoading(true);
    getPayment(id)
      .then((response) => {
        if (response.unavailable) {
          setNotAvailable(true);
          setPayment(null);
          return;
        }
        setNotAvailable(false);
        setPayment(response.payment);
      })
      .catch((err: unknown) => {
        if (err instanceof UnauthorizedError) {
          setUnauthorized(true);
          return;
        }
        setError((err as Error).message);
      })
      .finally(() => setLoading(false));
  }, [id]);

  const loadRefunds = useCallback(() => {
    if (!id) return;
    setRefundsLoading(true);
    listRefunds({ payment_id: id })
      .then((response) => {
        if (response.unavailable) {
          setRefundsUnavailable(true);
          setRefunds([]);
          return;
        }
        setRefundsUnavailable(false);
        setRefunds(response.items ?? []);
      })
      .catch(() => {
        setRefundsUnavailable(true);
        setRefunds([]);
      })
      .finally(() => setRefundsLoading(false));
  }, [id]);

  useEffect(() => {
    loadPayment();
    loadRefunds();
  }, [loadPayment, loadRefunds]);

  useEffect(() => {
    if (refundModalOpen && payment) {
      const refundedTotal = refunds.reduce((sum, item) => sum + Number(item.amount || 0), 0);
      const remaining = Math.max(Number(payment.amount) - refundedTotal, 0);
      setRefundAmount(String(remaining));
      setRefundProviderId("");
      setRefundIdempotencyKey(createIdempotencyKey());
      setRefundError(null);
      setRefundErrorDetail(null);
    }
  }, [payment, refundModalOpen, refunds]);

  const refundColumns = useMemo<Column<BillingRefund>[]>(
    () => [
      {
        key: "id",
        title: "Refund ID",
        render: (item) => (
          <div className="stack-inline" style={{ gap: 8 }}>
            <span>{item.id}</span>
            <CopyButton value={item.id} />
          </div>
        ),
      },
      {
        key: "amount",
        title: "Amount",
        render: (item) => formatMoney(item.amount, item.currency),
      },
      {
        key: "status",
        title: "Status",
        render: (item) => renderBadge(item.status, refundStatusBadge(item.status)),
      },
      {
        key: "refunded_at",
        title: "Refunded at",
        render: (item) => formatDateTime(item.refunded_at),
      },
      {
        key: "provider_refund_id",
        title: "Provider refund ID",
        render: (item) => item.provider_refund_id ?? "—",
      },
    ],
    [],
  );

  const canRefund = payment && payment.status !== "FAILED" && payment.status !== "REFUNDED_FULL";

  const handleRefund = async () => {
    if (!payment) return;
    setRefundError(null);
    setRefundErrorDetail(null);
    const amountValue = Number(refundAmount);
    if (!Number.isFinite(amountValue) || amountValue <= 0) {
      setRefundError("Amount must be a positive number");
      return;
    }
    try {
      const response = await refundPayment(payment.id, {
        amount: amountValue,
        currency: payment.currency,
        provider_refund_id: refundProviderId.trim() ? refundProviderId.trim() : undefined,
        idempotency_key: refundIdempotencyKey,
      });
      if (response.unavailable) {
        setRefundError("Refund endpoint unavailable");
        return;
      }
      if (response.refund) {
        showToast("success", `Refund created · ${response.refund.id}`);
        setRefundModalOpen(false);
        loadRefunds();
        loadPayment();
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to refund";
      setRefundError("Failed to refund payment");
      setRefundErrorDetail(message);
    }
  };

  if (unauthorized) {
    return <div className="card error-state">Unauthorized</div>;
  }

  if (loading) {
    return <div className="card">Loading payment...</div>;
  }

  if (notAvailable) {
    return <div className="card">Payments endpoint unavailable in this environment</div>;
  }

  if (!payment) {
    return <div className="card error-state">Payment not found</div>;
  }

  return (
    <div className="stack">
      <Toast toast={toast} />
      <section className="card">
        <div className="card__header" style={{ justifyContent: "space-between", gap: 16 }}>
          <div>
            <h2 style={{ marginTop: 0 }}>
              Payment {payment.id} {renderBadge(payment.status, paymentStatusBadge(payment.status))}
            </h2>
            <p className="muted">Invoice ID: {payment.invoice_id}</p>
          </div>
          <div className="stack-inline">
            <button type="button" className="ghost" onClick={() => navigate("/billing/payments")}>
              Back to payments
            </button>
            {canRefund ? (
              <button type="button" className="neft-btn-secondary" onClick={() => setRefundModalOpen(true)}>
                Refund
              </button>
            ) : null}
          </div>
        </div>
        <div className="explain-summary">
          <div className="explain-summary__card">
            <div className="explain-summary__label">Amount</div>
            <div className="explain-summary__value">{formatMoney(payment.amount, payment.currency)}</div>
          </div>
          <div className="explain-summary__card">
            <div className="explain-summary__label">Captured at</div>
            <div className="explain-summary__value">{formatDateTime(payment.captured_at)}</div>
          </div>
          <div className="explain-summary__card">
            <div className="explain-summary__label">Provider</div>
            <div className="explain-summary__value">{payment.provider}</div>
          </div>
          <div className="explain-summary__card">
            <div className="explain-summary__label">Provider payment ID</div>
            <div className="explain-summary__value">{payment.provider_payment_id ?? "—"}</div>
          </div>
        </div>
      </section>

      {error ? <div className="card error-state">{error}</div> : null}

      <section className="card">
        <h3 style={{ marginTop: 0 }}>Refunds</h3>
        {refundsUnavailable ? <div className="muted">Refunds endpoint unavailable</div> : null}
        <Table
          columns={refundColumns}
          data={refunds}
          loading={refundsLoading}
          emptyState={{ title: "No refunds", description: "Refunds will appear here once processed." }}
        />
      </section>

      <section className="card">
        <h3 style={{ marginTop: 0 }}>Audit</h3>
        <div className="stack-inline" style={{ gap: 8, marginBottom: 12 }}>
          <span>Audit event ID: {payment.audit_event_id}</span>
          <CopyButton value={payment.audit_event_id} />
        </div>
        <JsonViewer value={payment} redactionMode="audit" title="Payment payload" />
      </section>

      {refundModalOpen ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <h3 style={{ marginTop: 0 }}>Refund payment</h3>
            <label className="filter">
              Amount
              <input value={refundAmount} onChange={(event) => setRefundAmount(event.target.value)} type="number" />
            </label>
            <label className="filter">
              Provider refund ID (optional)
              <input value={refundProviderId} onChange={(event) => setRefundProviderId(event.target.value)} />
            </label>
            <label className="filter">
              Idempotency key
              <input value={refundIdempotencyKey} onChange={(event) => setRefundIdempotencyKey(event.target.value)} />
            </label>
            {refundError ? (
              <div className="card error-state">
                <div>{refundError}</div>
                {refundErrorDetail ? (
                  <div className="stack-inline" style={{ marginTop: 8 }}>
                    <span className="muted">{refundErrorDetail}</span>
                    <CopyButton value={refundErrorDetail} />
                  </div>
                ) : null}
              </div>
            ) : null}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
              <button type="button" className="ghost" onClick={() => setRefundModalOpen(false)}>
                Close
              </button>
              <button type="button" onClick={handleRefund} className="neft-btn-secondary">
                Refund
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default BillingPaymentDetailsPage;
