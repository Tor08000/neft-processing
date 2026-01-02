import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { listReconciliationLinks } from "../../api/billing";
import { UnauthorizedError } from "../../api/client";
import { CopyButton } from "../../components/CopyButton/CopyButton";
import { DateRangeFilter } from "../../components/Filters/DateRangeFilter";
import { SelectFilter } from "../../components/Filters/SelectFilter";
import { Table, type Column } from "../../components/Table/Table";
import { formatDateTime } from "../../utils/format";
import type { BillingReconciliationLink } from "../../types/billingFlows";
import { directionBadge, entityTypeBadge, formatMoney, linkStatusBadge, renderBadge } from "./billingUtils";

const STATUS_OPTIONS = ["PENDING", "MATCHED", "MISMATCHED"];
const ENTITY_OPTIONS = ["invoice", "payment", "refund"];

const toIsoDateTime = (value?: string) => {
  if (!value) return undefined;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return undefined;
  return date.toISOString();
};

const entityLink = (entityType: string, entityId: string) => {
  if (entityType === "invoice") return `/billing/invoices/${entityId}`;
  if (entityType === "payment") return `/billing/payments/${entityId}`;
  if (entityType === "refund") return `/billing/refunds`; // refunds list only
  return "/billing";
};

const BillingLinksPage: React.FC = () => {
  const navigate = useNavigate();
  const [links, setLinks] = useState<BillingReconciliationLink[]>([]);
  const [provider, setProvider] = useState("");
  const [status, setStatus] = useState("");
  const [entityType, setEntityType] = useState("");
  const [currency, setCurrency] = useState("");
  const [dateRange, setDateRange] = useState<{ from?: string; to?: string }>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notAvailable, setNotAvailable] = useState(false);
  const [unauthorized, setUnauthorized] = useState(false);

  const loadLinks = useCallback(() => {
    setIsLoading(true);
    setError(null);
    setUnauthorized(false);
    listReconciliationLinks({
      provider: provider || undefined,
      status: status || undefined,
      entity_type: entityType || undefined,
      currency: currency || undefined,
      date_from: toIsoDateTime(dateRange.from),
      date_to: toIsoDateTime(dateRange.to),
    })
      .then((response) => {
        if (response.unavailable) {
          setNotAvailable(true);
          setLinks([]);
          return;
        }
        setNotAvailable(false);
        setLinks(response.items ?? []);
      })
      .catch((err: unknown) => {
        if (err instanceof UnauthorizedError) {
          setUnauthorized(true);
          return;
        }
        setError((err as Error).message);
      })
      .finally(() => setIsLoading(false));
  }, [currency, dateRange.from, dateRange.to, entityType, provider, status]);

  useEffect(() => {
    loadLinks();
  }, [loadLinks]);

  const providerOptions = useMemo(() => {
    const values = new Set(links.map((item) => item.provider).filter(Boolean));
    return Array.from(values).map((value) => ({ label: value, value }));
  }, [links]);

  const currencyOptions = useMemo(() => {
    const values = new Set(links.map((item) => item.currency).filter(Boolean));
    return Array.from(values).map((value) => ({ label: value, value }));
  }, [links]);

  const columns = useMemo<Column<BillingReconciliationLink>[]>(
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
        key: "entity_type",
        title: "Entity type",
        render: (item) => renderBadge(item.entity_type, entityTypeBadge(item.entity_type)),
      },
      {
        key: "entity_id",
        title: "Entity ID",
        render: (item) => (
          <Link to={entityLink(item.entity_type, item.entity_id)} className="ghost">
            {item.entity_id}
          </Link>
        ),
      },
      {
        key: "provider",
        title: "Provider",
        render: (item) => item.provider,
      },
      {
        key: "currency",
        title: "Currency",
        render: (item) => item.currency,
      },
      {
        key: "expected_amount",
        title: "Expected amount",
        render: (item) => formatMoney(item.expected_amount, item.currency),
      },
      {
        key: "direction",
        title: "Direction",
        render: (item) => renderBadge(item.direction, directionBadge(item.direction)),
      },
      {
        key: "expected_at",
        title: "Expected at",
        render: (item) => formatDateTime(item.expected_at),
      },
      {
        key: "status",
        title: "Status",
        render: (item) => renderBadge(item.status, linkStatusBadge(item.status)),
      },
      {
        key: "run_id",
        title: "Run ID",
        render: (item) =>
          item.run_id ? (
            <button type="button" className="ghost" onClick={() => navigate(`/reconciliation/runs/${item.run_id}`)}>
              {item.run_id}
            </button>
          ) : (
            "—"
          ),
      },
      {
        key: "actions",
        title: "Actions",
        render: (item) => {
          if (item.status !== "MISMATCHED") return "—";
          if (!item.run_id) {
            return <span className="muted">Run reconciliation to generate discrepancies</span>;
          }
          return (
            <button type="button" className="ghost" onClick={() => navigate(`/reconciliation/runs/${item.run_id}`)}>
              Open discrepancies
            </button>
          );
        },
      },
      {
        key: "details",
        title: "Details",
        render: (item) => (
          <details>
            <summary>Details</summary>
            <div className="muted" style={{ marginTop: 8 }}>
              <div>Match key: {item.match_key ?? "—"}</div>
              <div>Last run: {item.last_run_id ?? item.run_id ?? "—"}</div>
              <div>Discrepancy ID: {item.discrepancy_id ?? "—"}</div>
            </div>
          </details>
        ),
      },
    ],
    [navigate],
  );

  if (unauthorized) {
    return <div className="card error-state">Unauthorized</div>;
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="card__header" style={{ justifyContent: "space-between", gap: 16 }}>
          <div>
            <h2 style={{ marginTop: 0 }}>Reconciliation links</h2>
            <p className="muted">Pending, matched, and mismatched reconciliation links.</p>
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
          <SelectFilter
            label="Entity type"
            value={entityType}
            onChange={setEntityType}
            options={ENTITY_OPTIONS.map((value) => ({ label: value, value }))}
          />
          <SelectFilter label="Currency" value={currency} onChange={setCurrency} options={currencyOptions} />
          <DateRangeFilter label="Expected at" from={dateRange.from} to={dateRange.to} onChange={setDateRange} />
        </div>
      </section>

      {notAvailable ? <div className="card">Links unavailable in this environment</div> : null}
      {error ? <div className="card error-state">{error}</div> : null}

      <Table
        columns={columns}
        data={links}
        loading={isLoading}
        emptyState={{ title: "No links pending", description: "Links will appear after payments and refunds." }}
      />
    </div>
  );
};

export default BillingLinksPage;
