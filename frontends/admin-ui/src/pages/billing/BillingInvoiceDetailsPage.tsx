import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getInvoice, listInvoicePayments, listReconciliationLinks, refundPayment } from "../../api/billing";
import { UnauthorizedError } from "../../api/client";
import { CopyButton } from "../../components/CopyButton/CopyButton";
import { Table, type Column } from "../../components/Table/Table";
import { Toast } from "../../components/common/Toast";
import { JsonViewer } from "../../components/common/JsonViewer";
import { useToast } from "../../components/Toast/useToast";
import { formatDateTime } from "../../utils/format";
import { createIdempotencyKey } from "../../utils/uuid";
import type { BillingInvoice, BillingPayment, BillingReconciliationLink } from "../../types/billingFlows";
import { withBase } from "@shared/lib/path";
import {
  formatMoney,
  invoiceStatusBadge,
  paymentStatusBadge,
  renderBadge,
  linkStatusBadge,
  entityTypeBadge,
  directionBadge,
} from "./billingUtils";

const BillingInvoiceDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { toast, showToast } = useToast();
  const [invoice, setInvoice] = useState<BillingInvoice | null>(null);
  const [payments, setPayments] = useState<BillingPayment[]>([]);
  const [links, setLinks] = useState<BillingReconciliationLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [paymentsLoading, setPaymentsLoading] = useState(true);
  const [linksLoading, setLinksLoading] = useState(false);
  const [linksUnavailable, setLinksUnavailable] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notAvailable, setNotAvailable] = useState(false);
  const [unauthorized, setUnauthorized] = useState(false);
  const [activeTab, setActiveTab] = useState<"payments" | "ledger" | "audit" | "links">("payments");

  const [refundModalOpen, setRefundModalOpen] = useState(false);
  const [refundPaymentTarget, setRefundPaymentTarget] = useState<BillingPayment | null>(null);
  const [refundAmount, setRefundAmount] = useState("");
  const [refundProviderId, setRefundProviderId] = useState("");
  const [refundIdempotencyKey, setRefundIdempotencyKey] = useState("");
  const [refundError, setRefundError] = useState<string | null>(null);
  const [refundErrorDetail, setRefundErrorDetail] = useState<string | null>(null);

  const loadInvoice = useCallback(() => {
    if (!id) return;
    setLoading(true);
    getInvoice(id)
      .then((response) => {
        if (response.unavailable) {
          setNotAvailable(true);
          setInvoice(null);
          return;
        }
        setNotAvailable(false);
        setInvoice(response.invoice);
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

  const loadPayments = useCallback(() => {
    if (!id) return;
    setPaymentsLoading(true);
    listInvoicePayments(id)
      .then((response) => {
        if (response.unavailable) {
          setNotAvailable(true);
          setPayments([]);
          return;
        }
        setNotAvailable(false);
        setPayments(response.items ?? []);
      })
      .catch((err: unknown) => {
        if (err instanceof UnauthorizedError) {
          setUnauthorized(true);
          return;
        }
        setError((err as Error).message);
      })
      .finally(() => setPaymentsLoading(false));
  }, [id]);

  const loadLinks = useCallback(() => {
    if (!id) return;
    setLinksLoading(true);
    listReconciliationLinks({ entity_type: "invoice", entity_id: id })
      .then((response) => {
        if (response.unavailable) {
          setLinksUnavailable(true);
          setLinks([]);
          return;
        }
        setLinksUnavailable(false);
        setLinks(response.items ?? []);
      })
      .catch(() => setLinks([]))
      .finally(() => setLinksLoading(false));
  }, [id]);

  useEffect(() => {
    loadInvoice();
    loadPayments();
  }, [loadInvoice, loadPayments]);

  useEffect(() => {
    if (activeTab === "links") {
      loadLinks();
    }
  }, [activeTab, loadLinks]);

  useEffect(() => {
    if (refundModalOpen && refundPaymentTarget) {
      setRefundAmount(String(refundPaymentTarget.amount));
      setRefundProviderId("");
      setRefundIdempotencyKey(createIdempotencyKey());
      setRefundError(null);
      setRefundErrorDetail(null);
    }
  }, [refundModalOpen, refundPaymentTarget]);

  const paymentColumns = useMemo<Column<BillingPayment>[]>(
    () => [
      {
        key: "id",
        title: "Payment ID",
        render: (item) => (
          <Link to={`/billing/payments/${item.id}`} className="ghost">
            {item.id}
          </Link>
        ),
      },
      {
        key: "provider",
        title: "Provider",
        render: (item) => item.provider,
      },
      {
        key: "amount",
        title: "Amount",
        render: (item) => formatMoney(item.amount, item.currency),
      },
      {
        key: "status",
        title: "Status",
        render: (item) => renderBadge(item.status, paymentStatusBadge(item.status)),
      },
      {
        key: "captured_at",
        title: "Captured at",
        render: (item) => formatDateTime(item.captured_at),
      },
      {
        key: "actions",
        title: "Actions",
        render: (item) => (
          <button
            type="button"
            className="ghost"
            onClick={() => {
              setRefundPaymentTarget(item);
              setRefundModalOpen(true);
            }}
            disabled={item.status === "FAILED" || item.status === "REFUNDED_FULL"}
          >
            Refund
          </button>
        ),
      },
    ],
    [],
  );

  const linkColumns = useMemo<Column<BillingReconciliationLink>[]>(
    () => [
      {
        key: "id",
        title: "Link ID",
        render: (item) => (
          <div className="stack-inline" style={{ gap: 8 }}>
            <span>{item.id}</span>
            <CopyButton value={item.id} />
          </div>
        ),
      },
      {
        key: "entity",
        title: "Entity",
        render: (item) => (
          <div className="stack-inline" style={{ gap: 8 }}>
            {renderBadge(item.entity_type, entityTypeBadge(item.entity_type))}
            <span>{item.entity_id}</span>
          </div>
        ),
      },
      {
        key: "direction",
        title: "Direction",
        render: (item) => renderBadge(item.direction, directionBadge(item.direction)),
      },
      {
        key: "expected",
        title: "Expected amount",
        render: (item) => formatMoney(item.expected_amount, item.currency),
      },
      {
        key: "status",
        title: "Status",
        render: (item) => renderBadge(item.status, linkStatusBadge(item.status)),
      },
      {
        key: "expected_at",
        title: "Expected at",
        render: (item) => formatDateTime(item.expected_at),
      },
      {
        key: "run",
        title: "Run",
        render: (item) =>
          item.run_id ? (
            <button type="button" className="ghost" onClick={() => navigate(`/reconciliation/runs/${item.run_id}`)}>
              {item.run_id}
            </button>
          ) : (
            "—"
          ),
      },
    ],
    [navigate],
  );

  const handleRefund = async () => {
    if (!refundPaymentTarget) return;
    setRefundError(null);
    setRefundErrorDetail(null);
    const amountValue = Number(refundAmount);
    if (!Number.isFinite(amountValue) || amountValue <= 0) {
      setRefundError("Amount must be a positive number");
      return;
    }
    try {
      const response = await refundPayment(refundPaymentTarget.id, {
        amount: amountValue,
        currency: refundPaymentTarget.currency,
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
        loadPayments();
        loadLinks();
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
    return <div className="card">Loading invoice...</div>;
  }

  if (notAvailable) {
    return <div className="card">Billing endpoints unavailable in this environment</div>;
  }

  if (!invoice) {
    return <div className="card error-state">Invoice not found</div>;
  }

  return (
    <div className="stack">
      <Toast toast={toast} />
      <section className="card">
        <div className="card__header" style={{ justifyContent: "space-between", gap: 16 }}>
          <div>
            <h2 style={{ marginTop: 0 }}>
              Invoice {invoice.invoice_number} {renderBadge(invoice.status, invoiceStatusBadge(invoice.status))}
            </h2>
            <p className="muted">Invoice ID: {invoice.id}</p>
          </div>
          <div className="stack-inline">
            <button type="button" className="ghost" onClick={() => navigate("/billing/invoices")}>
              Back to invoices
            </button>
          </div>
        </div>
        <div className="explain-summary">
          <div className="explain-summary__card">
            <div className="explain-summary__label">Amount total</div>
            <div className="explain-summary__value">{formatMoney(invoice.amount_total, invoice.currency)}</div>
          </div>
          <div className="explain-summary__card">
            <div className="explain-summary__label">Amount paid</div>
            <div className="explain-summary__value">{formatMoney(invoice.amount_paid, invoice.currency)}</div>
          </div>
          <div className="explain-summary__card">
            <div className="explain-summary__label">Issued at</div>
            <div className="explain-summary__value">{formatDateTime(invoice.issued_at)}</div>
          </div>
          <div className="explain-summary__card">
            <div className="explain-summary__label">Due at</div>
            <div className="explain-summary__value">{formatDateTime(invoice.due_at ?? undefined)}</div>
          </div>
        </div>
      </section>

      {error ? <div className="card error-state">{error}</div> : null}

      <div className="card" style={{ padding: 12 }}>
        <div className="pill-list">
          <button
            type="button"
            className={`pill pill--outline${activeTab === "payments" ? " pill--accent" : ""}`}
            onClick={() => setActiveTab("payments")}
          >
            Payments
          </button>
          <button
            type="button"
            className={`pill pill--outline${activeTab === "ledger" ? " pill--accent" : ""}`}
            onClick={() => setActiveTab("ledger")}
          >
            Ledger
          </button>
          <button
            type="button"
            className={`pill pill--outline${activeTab === "audit" ? " pill--accent" : ""}`}
            onClick={() => setActiveTab("audit")}
          >
            Audit
          </button>
          <button
            type="button"
            className={`pill pill--outline${activeTab === "links" ? " pill--accent" : ""}`}
            onClick={() => setActiveTab("links")}
          >
            Reconciliation Links
          </button>
        </div>
      </div>

      {activeTab === "payments" ? (
        <Table
          columns={paymentColumns}
          data={payments}
          loading={paymentsLoading}
          emptyState={{ title: "No payments", description: "Capture payments to see them here." }}
        />
      ) : null}

      {activeTab === "ledger" ? (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Ledger</h3>
          <div className="stack-inline" style={{ gap: 8 }}>
            <span>{invoice.ledger_tx_id}</span>
            <CopyButton value={invoice.ledger_tx_id} />
            <a
              href={withBase(`/ledger/transactions/${invoice.ledger_tx_id}`)}
              target="_blank"
              rel="noreferrer"
              className="ghost"
            >
              Open ledger transaction
            </a>
          </div>
        </div>
      ) : null}

      {activeTab === "audit" ? (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Audit</h3>
          <div className="stack-inline" style={{ gap: 8, marginBottom: 12 }}>
            <span>Audit event ID: {invoice.audit_event_id}</span>
            <CopyButton value={invoice.audit_event_id} />
          </div>
          <JsonViewer value={invoice} redactionMode="audit" title="Invoice payload" />
        </div>
      ) : null}

      {activeTab === "links" ? (
        <>
          {linksUnavailable ? <div className="card">Links unavailable in this environment</div> : null}
          <Table
            columns={linkColumns}
            data={links}
            loading={linksLoading}
            emptyState={{ title: "No links pending", description: "Reconciliation links will appear here." }}
          />
        </>
      ) : null}

      {refundModalOpen && refundPaymentTarget ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <h3 style={{ marginTop: 0 }}>Refund payment</h3>
            <div className="muted" style={{ marginBottom: 8 }}>
              Payment {refundPaymentTarget.id} · Available {formatMoney(refundPaymentTarget.amount, refundPaymentTarget.currency)}
            </div>
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

export default BillingInvoiceDetailsPage;
