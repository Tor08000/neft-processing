import React, { Suspense, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchFinanceInvoices } from "../../api/finance";
import type { FinanceInvoiceSummary } from "../../types/finance";
import { Table, type Column } from "../../components/Table/Table";
import { Pagination } from "../../components/Pagination/Pagination";
import { Loader } from "../../components/Loader/Loader";
import { getIsoDate } from "../../utils/format";
import { extractRequestId } from "../ops/opsUtils";

const DateRangeFilter = React.lazy(() =>
  import("../../components/Filters/DateRangeFilter").then((mod) => ({ default: mod.DateRangeFilter })),
);

const today = new Date();
const sevenDaysAgo = new Date(today);
sevenDaysAgo.setDate(today.getDate() - 6);

type DateRange = {
  from?: string;
  to?: string;
};

const defaultRange: DateRange = {
  from: getIsoDate(sevenDaysAgo),
  to: getIsoDate(today),
};

export const InvoicesPage: React.FC = () => {
  const navigate = useNavigate();
  const [limit] = useState(50);
  const [offset, setOffset] = useState(0);
  const [status, setStatus] = useState("");
  const [orgId, setOrgId] = useState("");
  const [dateRange, setDateRange] = useState<DateRange>(defaultRange);
  const [debouncedFilters, setDebouncedFilters] = useState({
    status: "",
    orgId: "",
    dateRange: defaultRange,
    offset: 0,
  });

  useEffect(() => {
    const handler = window.setTimeout(() => {
      setDebouncedFilters({ status, orgId, dateRange, offset });
    }, 400);
    return () => window.clearTimeout(handler);
  }, [status, orgId, dateRange, offset]);

  const filters = useMemo(
    () => ({
      status: debouncedFilters.status || undefined,
      org_id: debouncedFilters.orgId || undefined,
      from: debouncedFilters.dateRange.from,
      to: debouncedFilters.dateRange.to,
      limit,
      offset: debouncedFilters.offset,
    }),
    [debouncedFilters, limit],
  );

  const { data, isFetching, isLoading, error, refetch } = useQuery({
    queryKey: ["finance-invoices", filters],
    queryFn: () => fetchFinanceInvoices(filters),
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  const columns: Column<FinanceInvoiceSummary>[] = [
    { key: "id", title: "Invoice ID", render: (row) => row.id },
    { key: "status", title: "Status", render: (row) => row.status },
    { key: "org_id", title: "Org", render: (row) => row.org_id ?? "—" },
    {
      key: "period",
      title: "Period",
      render: (row) =>
        row.period_start || row.period_end ? `${row.period_start ?? "—"} → ${row.period_end ?? "—"}` : "—",
    },
    { key: "due_at", title: "Due", render: (row) => row.due_at ?? "—" },
    { key: "paid_at", title: "Paid", render: (row) => row.paid_at ?? "—" },
    {
      key: "total",
      title: "Total",
      render: (row) => `${row.total ?? "—"} ${row.currency ?? ""}`,
    },
  ];

  return (
    <div className="stack">
      <div className="page-header">
        <h1>Invoices</h1>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button type="button" className="ghost" onClick={() => refetch()}>
            Refresh
          </button>
          {(isLoading || isFetching) && <Loader label="Loading invoices" />}
        </div>
      </div>

      <Table
        columns={columns}
        data={items}
        loading={isLoading}
        toolbar={
          <Suspense fallback={<Loader label="Loading filters" />}>
            <div className="filters">
              <DateRangeFilter
                label="Period"
                from={dateRange.from}
                to={dateRange.to}
                onChange={(range) => {
                  setOffset(0);
                  setDateRange(range);
                }}
              />
              <div className="filter">
                <span className="label">Org</span>
                <input
                  placeholder="org_id"
                  value={orgId}
                  onChange={(event) => {
                    setOffset(0);
                    setOrgId(event.target.value);
                  }}
                />
              </div>
              <div className="filter">
                <span className="label">Status</span>
                <input
                  placeholder="status"
                  value={status}
                  onChange={(event) => {
                    setOffset(0);
                    setStatus(event.target.value);
                  }}
                />
              </div>
            </div>
          </Suspense>
        }
        errorState={
          error
            ? {
                title: "Failed to load invoices",
                description: (error as Error).message,
                actionLabel: "Retry",
                actionOnClick: () => refetch(),
                requestId: extractRequestId(error),
              }
            : undefined
        }
        footer={
          <div className="table-footer__content">
            <Pagination total={total} limit={limit} offset={offset} onChange={(value) => setOffset(value)} />
          </div>
        }
        onRowClick={(row) => navigate(`/finance/invoices/${row.id}`)}
      />
    </div>
  );
};

export default InvoicesPage;
