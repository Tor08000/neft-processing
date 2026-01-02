import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  captureInvoicePayment,
  createInvoice,
  listInvoices,
} from "../../api/billing";
import { UnauthorizedError } from "../../api/client";
import { CopyButton } from "../../components/CopyButton/CopyButton";
import { DateRangeFilter } from "../../components/Filters/DateRangeFilter";
import { SelectFilter } from "../../components/Filters/SelectFilter";
import { Table, type Column } from "../../components/Table/Table";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import { formatDateTime } from "../../utils/format";
import { createIdempotencyKey } from "../../utils/uuid";
import type { BillingInvoice } from "../../types/billingFlows";
import { formatMoney, invoiceStatusBadge, renderBadge } from "./billingUtils";

const STATUS_OPTIONS = ["ISSUED", "PARTIALLY_PAID", "PAID", "VOID"];
const CURRENCY_OPTIONS = ["RUB", "USD", "EUR"];

const toIsoDateTime = (value?: string) => {
  if (!value) return undefined;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return undefined;
  return date.toISOString();
};

const buildRemainingAmount = (invoice: BillingInvoice) => {
  const total = Number(invoice.amount_total);
  const paid = Number(invoice.amount_paid);
  return Math.max(total - paid, 0);
};

const BillingInvoicesPage: React.FC = () => {
  const navigate = useNavigate();
  const { toast, showToast } = useToast();
  const [invoices, setInvoices] = useState<BillingInvoice[]>([]);
  const [status, setStatus] = useState("");
  const [clientId, setClientId] = useState("");
  const [caseId, setCaseId] = useState("");
  const [currency, setCurrency] = useState("");
  const [search, setSearch] = useState("");
  const [dateRange, setDateRange] = useState<{ from?: string; to?: string }>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notAvailable, setNotAvailable] = useState(false);
  const [unauthorized, setUnauthorized] = useState(false);

  const [issueModalOpen, setIssueModalOpen] = useState(false);
  const [issueClientId, setIssueClientId] = useState("");
  const [issueCaseId, setIssueCaseId] = useState("");
  const [issueCurrency, setIssueCurrency] = useState("RUB");
  const [issueAmount, setIssueAmount] = useState("");
  const [issueDueAt, setIssueDueAt] = useState("");
  const [issueIdempotencyKey, setIssueIdempotencyKey] = useState("");
  const [issueError, setIssueError] = useState<string | null>(null);
  const [issueErrorDetail, setIssueErrorDetail] = useState<string | null>(null);
  const [issueResult, setIssueResult] = useState<BillingInvoice | null>(null);

  const [captureModalOpen, setCaptureModalOpen] = useState(false);
  const [captureInvoice, setCaptureInvoice] = useState<BillingInvoice | null>(null);
  const [captureProvider, setCaptureProvider] = useState("bank_stub");
  const [captureProviderId, setCaptureProviderId] = useState("");
  const [captureAmount, setCaptureAmount] = useState("");
  const [captureIdempotencyKey, setCaptureIdempotencyKey] = useState("");
  const [captureError, setCaptureError] = useState<string | null>(null);
  const [captureErrorDetail, setCaptureErrorDetail] = useState<string | null>(null);
  const [captureResultId, setCaptureResultId] = useState<string | null>(null);

  const loadInvoices = useCallback(() => {
    setIsLoading(true);
    setError(null);
    setUnauthorized(false);
    listInvoices({
      client_id: clientId || undefined,
      status: status || undefined,
      date_from: toIsoDateTime(dateRange.from),
      date_to: toIsoDateTime(dateRange.to),
    })
      .then((data) => {
        if (data.unavailable) {
          setNotAvailable(true);
          setInvoices([]);
          return;
        }
        setNotAvailable(false);
        setInvoices(data.items ?? []);
      })
      .catch((err: unknown) => {
        if (err instanceof UnauthorizedError) {
          setUnauthorized(true);
          return;
        }
        setError((err as Error).message);
      })
      .finally(() => setIsLoading(false));
  }, [clientId, dateRange.from, dateRange.to, status]);

  useEffect(() => {
    loadInvoices();
  }, [loadInvoices]);

  useEffect(() => {
    if (issueModalOpen) {
      setIssueIdempotencyKey(createIdempotencyKey());
      setIssueError(null);
      setIssueErrorDetail(null);
      setIssueResult(null);
    }
  }, [issueModalOpen]);

  useEffect(() => {
    if (captureModalOpen && captureInvoice) {
      setCaptureProvider("bank_stub");
      setCaptureProviderId("");
      setCaptureAmount(String(buildRemainingAmount(captureInvoice)));
      setCaptureIdempotencyKey(createIdempotencyKey());
      setCaptureError(null);
      setCaptureErrorDetail(null);
      setCaptureResultId(null);
    }
  }, [captureModalOpen, captureInvoice]);

  const filteredInvoices = useMemo(() => {
    return invoices.filter((invoice) => {
      if (caseId && invoice.case_id !== caseId) return false;
      if (currency && invoice.currency !== currency) return false;
      if (search) {
        const target = search.toLowerCase();
        if (!invoice.invoice_number.toLowerCase().includes(target) && !invoice.id.toLowerCase().includes(target)) {
          return false;
        }
      }
      return true;
    });
  }, [caseId, currency, invoices, search]);

  const columns = useMemo<Column<BillingInvoice>[]>(
    () => [
      {
        key: "number",
        title: "Invoice number",
        render: (item) => (
          <Link to={`/billing/invoices/${item.id}`} className="ghost">
            {item.invoice_number}
          </Link>
        ),
      },
      {
        key: "id",
        title: "Invoice ID",
        render: (item) => (
          <div className="stack-inline" style={{ gap: 8 }}>
            <span>{item.id}</span>
            <CopyButton value={item.id} />
          </div>
        ),
      },
      {
        key: "client",
        title: "Client ID",
        render: (item) => item.client_id,
      },
      {
        key: "case",
        title: "Case ID",
        render: (item) =>
          item.case_id ? (
            <Link to={`/cases/${item.case_id}`} className="ghost">
              {item.case_id}
            </Link>
          ) : (
            "—"
          ),
      },
      {
        key: "currency",
        title: "Currency",
        render: (item) => item.currency,
      },
      {
        key: "amount_total",
        title: "Amount total",
        render: (item) => formatMoney(item.amount_total, item.currency),
      },
      {
        key: "amount_paid",
        title: "Amount paid",
        render: (item) => formatMoney(item.amount_paid, item.currency),
      },
      {
        key: "status",
        title: "Status",
        render: (item) => renderBadge(item.status, invoiceStatusBadge(item.status)),
      },
      {
        key: "issued_at",
        title: "Issued at",
        render: (item) => formatDateTime(item.issued_at),
      },
      {
        key: "due_at",
        title: "Due at",
        render: (item) => formatDateTime(item.due_at ?? undefined),
      },
      {
        key: "actions",
        title: "Actions",
        render: (item) => (
          <div className="stack-inline">
            <button
              type="button"
              className="ghost"
              onClick={(event) => {
                event.stopPropagation();
                setCaptureInvoice(item);
                setCaptureModalOpen(true);
              }}
              disabled={item.status === "PAID" || item.status === "VOID"}
            >
              Capture payment
            </button>
          </div>
        ),
      },
    ],
    [],
  );

  const handleIssueInvoice = async () => {
    setIssueError(null);
    setIssueErrorDetail(null);
    setIssueResult(null);
    if (!issueClientId.trim()) {
      setIssueError("Client ID is required");
      return;
    }
    if (!issueCurrency) {
      setIssueError("Currency is required");
      return;
    }
    const amountValue = Number(issueAmount);
    if (!Number.isFinite(amountValue) || amountValue <= 0) {
      setIssueError("Amount must be a positive number");
      return;
    }
    try {
      const response = await createInvoice({
        client_id: issueClientId.trim(),
        case_id: issueCaseId.trim() ? issueCaseId.trim() : undefined,
        currency: issueCurrency,
        amount_total: amountValue,
        due_at: toIsoDateTime(issueDueAt),
        idempotency_key: issueIdempotencyKey,
      });
      if (response.unavailable) {
        setIssueError("Invoice issue endpoint unavailable");
        return;
      }
      if (response.invoice) {
        setIssueResult(response.invoice);
        showToast("success", `Invoice issued · ${response.invoice.invoice_number}`);
        loadInvoices();
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to issue invoice";
      setIssueError("Failed to issue invoice");
      setIssueErrorDetail(message);
    }
  };

  const handleCapturePayment = async () => {
    if (!captureInvoice) return;
    setCaptureError(null);
    setCaptureErrorDetail(null);
    setCaptureResultId(null);
    const amountValue = Number(captureAmount);
    if (!Number.isFinite(amountValue) || amountValue <= 0) {
      setCaptureError("Amount must be a positive number");
      return;
    }
    try {
      const response = await captureInvoicePayment(captureInvoice.id, {
        provider: captureProvider,
        provider_payment_id: captureProviderId.trim() ? captureProviderId.trim() : undefined,
        amount: amountValue,
        currency: captureInvoice.currency,
        idempotency_key: captureIdempotencyKey,
      });
      if (response.unavailable) {
        setCaptureError("Capture endpoint unavailable");
        return;
      }
      if (response.payment) {
        setCaptureResultId(response.payment.id);
        showToast("success", `Payment captured · ${response.payment.id}`);
        loadInvoices();
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to capture payment";
      setCaptureError("Failed to capture payment");
      setCaptureErrorDetail(message);
    }
  };

  if (unauthorized) {
    return <div className="card error-state">Unauthorized</div>;
  }

  return (
    <div className="stack">
      <Toast toast={toast} />
      <section className="card">
        <div className="card__header" style={{ justifyContent: "space-between", gap: 16 }}>
          <div>
            <h2 style={{ marginTop: 0 }}>Invoices</h2>
            <p className="muted">Issue invoices and capture incoming payments.</p>
          </div>
          <div className="stack-inline">
            <button type="button" className="neft-btn-secondary" onClick={() => setIssueModalOpen(true)}>
              Issue invoice
            </button>
          </div>
        </div>
        <div className="filters">
          <SelectFilter
            label="Status"
            value={status}
            onChange={setStatus}
            options={STATUS_OPTIONS.map((value) => ({ label: value, value }))}
          />
          <label className="filter">
            Client ID
            <input value={clientId} onChange={(event) => setClientId(event.target.value)} />
          </label>
          <label className="filter">
            Case ID
            <input value={caseId} onChange={(event) => setCaseId(event.target.value)} />
          </label>
          <SelectFilter
            label="Currency"
            value={currency}
            onChange={setCurrency}
            options={CURRENCY_OPTIONS.map((value) => ({ label: value, value }))}
          />
          <label className="filter">
            Search
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Invoice number or ID" />
          </label>
          <DateRangeFilter label="Issued at" from={dateRange.from} to={dateRange.to} onChange={setDateRange} />
        </div>
      </section>

      {notAvailable ? <div className="card">Billing endpoints unavailable in this environment</div> : null}
      {error ? <div className="card error-state">{error}</div> : null}

      <Table
        columns={columns}
        data={filteredInvoices}
        loading={isLoading}
        emptyState={{ title: "No invoices found", description: "Try adjusting filters or issue a new invoice." }}
        onRowClick={(row) => navigate(`/billing/invoices/${row.id}`)}
      />

      {issueModalOpen ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <h3 style={{ marginTop: 0 }}>Issue invoice</h3>
            <label className="filter">
              Client ID
              <input value={issueClientId} onChange={(event) => setIssueClientId(event.target.value)} />
            </label>
            <label className="filter">
              Case ID (optional)
              <input value={issueCaseId} onChange={(event) => setIssueCaseId(event.target.value)} />
            </label>
            <label className="filter">
              Currency
              <select value={issueCurrency} onChange={(event) => setIssueCurrency(event.target.value)}>
                {CURRENCY_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>
            <label className="filter">
              Amount total
              <input value={issueAmount} onChange={(event) => setIssueAmount(event.target.value)} type="number" />
            </label>
            <label className="filter">
              Due at (optional)
              <input value={issueDueAt} onChange={(event) => setIssueDueAt(event.target.value)} type="datetime-local" />
            </label>
            <details className="audit-advanced" style={{ marginBottom: 12 }}>
              <summary>Advanced</summary>
              <label className="filter">
                Idempotency key
                <input value={issueIdempotencyKey} onChange={(event) => setIssueIdempotencyKey(event.target.value)} />
              </label>
            </details>
            {issueError ? (
              <div className="card error-state">
                <div>{issueError}</div>
                {issueErrorDetail ? (
                  <div className="stack-inline" style={{ marginTop: 8 }}>
                    <span className="muted">{issueErrorDetail}</span>
                    <CopyButton value={issueErrorDetail} />
                  </div>
                ) : null}
              </div>
            ) : null}
            {issueResult ? (
              <div className="card">
                <div>Invoice issued</div>
                <div className="stack-inline" style={{ gap: 8 }}>
                  <strong>{issueResult.invoice_number}</strong>
                  <CopyButton value={issueResult.id} />
                </div>
                <div className="muted">Invoice ID: {issueResult.id}</div>
              </div>
            ) : null}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
              <button type="button" className="ghost" onClick={() => setIssueModalOpen(false)}>
                Close
              </button>
              <button type="button" onClick={handleIssueInvoice} className="neft-btn-secondary">
                Issue invoice
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {captureModalOpen && captureInvoice ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <h3 style={{ marginTop: 0 }}>Capture payment</h3>
            <div className="muted" style={{ marginBottom: 8 }}>
              Invoice {captureInvoice.invoice_number} · Remaining {formatMoney(buildRemainingAmount(captureInvoice), captureInvoice.currency)}
            </div>
            <label className="filter">
              Provider
              <input value={captureProvider} onChange={(event) => setCaptureProvider(event.target.value)} />
            </label>
            <label className="filter">
              Provider payment ID (optional)
              <input value={captureProviderId} onChange={(event) => setCaptureProviderId(event.target.value)} />
            </label>
            <label className="filter">
              Amount
              <input value={captureAmount} onChange={(event) => setCaptureAmount(event.target.value)} type="number" />
            </label>
            <label className="filter">
              Currency
              <input value={captureInvoice.currency} readOnly />
            </label>
            <label className="filter">
              Idempotency key
              <input value={captureIdempotencyKey} onChange={(event) => setCaptureIdempotencyKey(event.target.value)} />
            </label>
            {captureError ? (
              <div className="card error-state">
                <div>{captureError}</div>
                {captureErrorDetail ? (
                  <div className="stack-inline" style={{ marginTop: 8 }}>
                    <span className="muted">{captureErrorDetail}</span>
                    <CopyButton value={captureErrorDetail} />
                  </div>
                ) : null}
              </div>
            ) : null}
            {captureResultId ? (
              <div className="card">
                <div>Payment captured</div>
                <div className="stack-inline" style={{ gap: 8 }}>
                  <span>{captureResultId}</span>
                  <CopyButton value={captureResultId} />
                </div>
                <div className="muted">Reconciliation link status: check Links tab for latest status.</div>
              </div>
            ) : null}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
              <button type="button" className="ghost" onClick={() => setCaptureModalOpen(false)}>
                Close
              </button>
              <button type="button" onClick={handleCapturePayment} className="neft-btn-secondary">
                Capture payment
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default BillingInvoicesPage;
