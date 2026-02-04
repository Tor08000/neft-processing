import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { listRefunds } from "../../api/billing";
import { UnauthorizedError } from "../../api/client";
import { CopyButton } from "../../components/CopyButton/CopyButton";
import { DateRangeFilter } from "../../components/Filters/DateRangeFilter";
import { SelectFilter } from "../../components/Filters/SelectFilter";
import { Table, type Column } from "../../components/Table/Table";
import { formatDateTime } from "../../utils/format";
import type { BillingRefund } from "../../types/billingFlows";
import { formatMoney, refundStatusBadge, renderBadge } from "./billingUtils";
import { AdminUnauthorizedPage } from "../admin/AdminStatusPages";

const STATUS_OPTIONS = ["REFUNDED", "FAILED"];

const toIsoDateTime = (value?: string) => {
  if (!value) return undefined;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return undefined;
  return date.toISOString();
};

const BillingRefundsPage: React.FC = () => {
  const [refunds, setRefunds] = useState<BillingRefund[]>([]);
  const [provider, setProvider] = useState("");
  const [status, setStatus] = useState("");
  const [dateRange, setDateRange] = useState<{ from?: string; to?: string }>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notAvailable, setNotAvailable] = useState(false);
  const [unauthorized, setUnauthorized] = useState(false);

  const loadRefunds = useCallback(() => {
    setIsLoading(true);
    setError(null);
    setUnauthorized(false);
    listRefunds({
      provider: provider || undefined,
      status: status || undefined,
      date_from: toIsoDateTime(dateRange.from),
      date_to: toIsoDateTime(dateRange.to),
    })
      .then((response) => {
        if (response.unavailable) {
          setNotAvailable(true);
          setRefunds([]);
          return;
        }
        setNotAvailable(false);
        setRefunds(response.items ?? []);
      })
      .catch((err: unknown) => {
        if (err instanceof UnauthorizedError) {
          setUnauthorized(true);
          return;
        }
        setError((err as Error).message);
      })
      .finally(() => setIsLoading(false));
  }, [dateRange.from, dateRange.to, provider, status]);

  useEffect(() => {
    loadRefunds();
  }, [loadRefunds]);

  const providerOptions = useMemo(() => {
    const values = new Set(
      refunds
        .map((item) => item.provider)
        .filter((value): value is string => Boolean(value)),
    );
    return Array.from(values).map((value) => ({ label: value, value }));
  }, [refunds]);

  const columns = useMemo<Column<BillingRefund>[]>(
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
        key: "payment_id",
        title: "Payment ID",
        render: (item) => (
          <Link to={`/billing/payments/${item.payment_id}`} className="ghost">
            {item.payment_id}
          </Link>
        ),
      },
      {
        key: "invoice_id",
        title: "Invoice ID",
        render: (item) =>
          item.invoice_id ? (
            <Link to={`/billing/invoices/${item.invoice_id}`} className="ghost">
              {item.invoice_id}
            </Link>
          ) : (
            "—"
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

  if (unauthorized) {
    return <AdminUnauthorizedPage />;
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="card__header" style={{ justifyContent: "space-between", gap: 16 }}>
          <div>
            <h2 style={{ marginTop: 0 }}>Refunds</h2>
            <p className="muted">Refunded payments and status updates.</p>
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
          <DateRangeFilter label="Refunded at" from={dateRange.from} to={dateRange.to} onChange={setDateRange} />
        </div>
      </section>

      {notAvailable ? <div className="card">Refunds endpoint unavailable in this environment</div> : null}
      {error ? <div className="card error-state">{error}</div> : null}

      <Table
        columns={columns}
        data={refunds}
        loading={isLoading}
        emptyState={{ title: "No refunds", description: "Refunds will appear here." }}
      />
    </div>
  );
};

export default BillingRefundsPage;
