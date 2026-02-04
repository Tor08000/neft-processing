import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { listPayments } from "../../api/billing";
import { UnauthorizedError } from "../../api/client";
import { CopyButton } from "../../components/CopyButton/CopyButton";
import { DateRangeFilter } from "../../components/Filters/DateRangeFilter";
import { SelectFilter } from "../../components/Filters/SelectFilter";
import { Table, type Column } from "../../components/Table/Table";
import { formatDateTime } from "../../utils/format";
import type { BillingPayment } from "../../types/billingFlows";
import { formatMoney, paymentStatusBadge, linkStatusBadge, renderBadge } from "./billingUtils";
import { AdminUnauthorizedPage } from "../admin/AdminStatusPages";

const STATUS_OPTIONS = ["CAPTURED", "FAILED", "REFUNDED_PARTIAL", "REFUNDED_FULL"];

const toIsoDateTime = (value?: string) => {
  if (!value) return undefined;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return undefined;
  return date.toISOString();
};

const BillingPaymentsPage: React.FC = () => {
  const navigate = useNavigate();
  const [payments, setPayments] = useState<BillingPayment[]>([]);
  const [provider, setProvider] = useState("");
  const [status, setStatus] = useState("");
  const [invoiceId, setInvoiceId] = useState("");
  const [search, setSearch] = useState("");
  const [dateRange, setDateRange] = useState<{ from?: string; to?: string }>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notAvailable, setNotAvailable] = useState(false);
  const [unauthorized, setUnauthorized] = useState(false);

  const loadPayments = useCallback(() => {
    setIsLoading(true);
    setError(null);
    setUnauthorized(false);
    listPayments({
      provider: provider || undefined,
      status: status || undefined,
      invoice_id: invoiceId || undefined,
      search: search || undefined,
      date_from: toIsoDateTime(dateRange.from),
      date_to: toIsoDateTime(dateRange.to),
    })
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
      .finally(() => setIsLoading(false));
  }, [dateRange.from, dateRange.to, invoiceId, provider, search, status]);

  useEffect(() => {
    loadPayments();
  }, [loadPayments]);

  const providerOptions = useMemo(() => {
    const values = new Set(payments.map((item) => item.provider).filter(Boolean));
    return Array.from(values).map((value) => ({ label: value, value }));
  }, [payments]);

  const columns = useMemo<Column<BillingPayment>[]>(
    () => [
      {
        key: "id",
        title: "Payment ID",
        render: (item) => (
          <div className="stack-inline" style={{ gap: 8 }}>
            <Link to={`/billing/payments/${item.id}`} className="ghost">
              {item.id}
            </Link>
            <CopyButton value={item.id} />
          </div>
        ),
      },
      {
        key: "invoice",
        title: "Invoice ID",
        render: (item) => (
          <Link to={`/billing/invoices/${item.invoice_id}`} className="ghost">
            {item.invoice_id}
          </Link>
        ),
      },
      {
        key: "provider",
        title: "Provider",
        render: (item) => item.provider,
      },
      {
        key: "provider_payment_id",
        title: "Provider payment ID",
        render: (item) => item.provider_payment_id ?? "—",
      },
      {
        key: "amount",
        title: "Amount",
        render: (item) => formatMoney(item.amount, item.currency),
      },
      {
        key: "currency",
        title: "Currency",
        render: (item) => item.currency,
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
        key: "link_status",
        title: "Reconciliation",
        render: (item) =>
          item.reconciliation_status ? renderBadge(item.reconciliation_status, linkStatusBadge(item.reconciliation_status)) : "—",
      },
    ],
    [],
  );

  if (unauthorized) {
    return <AdminUnauthorizedPage />;
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="card__header" style={{ justifyContent: "space-between", gap: 16 }}>
          <div>
            <h2 style={{ marginTop: 0 }}>Payments</h2>
            <p className="muted">Captured payments and reconciliation status.</p>
          </div>
        </div>
        <div className="filters">
          <SelectFilter label="Provider" value={provider} onChange={setProvider} options={providerOptions} />
          <SelectFilter
            label="Status"
            value={status}
            onChange={setStatus}
            options={STATUS_OPTIONS.map((value) => ({ label: value, value }))}
          />
          <label className="filter">
            Invoice ID
            <input value={invoiceId} onChange={(event) => setInvoiceId(event.target.value)} />
          </label>
          <label className="filter">
            Search
            <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Payment ID" />
          </label>
          <DateRangeFilter label="Captured at" from={dateRange.from} to={dateRange.to} onChange={setDateRange} />
        </div>
      </section>

      {notAvailable ? <div className="card">Payments endpoint unavailable in this environment</div> : null}
      {error ? <div className="card error-state">{error}</div> : null}

      <Table
        columns={columns}
        data={payments}
        loading={isLoading}
        emptyState={{ title: "No payments", description: "Captured payments will appear here." }}
        onRowClick={(row) => navigate(`/billing/payments/${row.id}`)}
      />
    </div>
  );
};

export default BillingPaymentsPage;
