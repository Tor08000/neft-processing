import React, { Suspense, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchPayoutBatches } from "../../api/payouts";
import { PayoutStateBadge } from "../../components/PayoutStateBadge/PayoutStateBadge";
import { Pagination } from "../../components/Pagination/Pagination";
import { Table, type Column } from "../../components/Table/Table";
import { CopyButton } from "../../components/CopyButton/CopyButton";
import { Loader } from "../../components/Loader/Loader";
import { PayoutBatchSummary, PayoutState } from "../../types/payouts";
import { formatRub, getIsoDate } from "../../utils/format";
import { useToast } from "../../components/Toast/useToast";
import { Toast } from "../../components/Toast/Toast";

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

const weekStartOffset = today.getDay() === 0 ? 6 : today.getDay() - 1;
const QUICK_PRESETS = [
  { label: "Today", range: { from: getIsoDate(today), to: getIsoDate(today) } },
  {
    label: "This week",
    range: {
      from: getIsoDate(new Date(today.getFullYear(), today.getMonth(), today.getDate() - weekStartOffset)),
      to: getIsoDate(today),
    },
  },
  {
    label: "This month",
    range: {
      from: getIsoDate(new Date(today.getFullYear(), today.getMonth(), 1)),
      to: getIsoDate(today),
    },
  },
];

const ALL_STATES: PayoutState[] = ["READY", "SENT", "SETTLED", "FAILED", "DRAFT"];

export const PayoutsList: React.FC = () => {
  const navigate = useNavigate();
  const { toast, showToast } = useToast();
  const [limit] = useState(50);
  const [offset, setOffset] = useState(0);
  const [dateRange, setDateRange] = useState<DateRange>(defaultRange);
  const [partnerId, setPartnerId] = useState("");
  const [states, setStates] = useState<PayoutState[]>([]);
  const [debouncedFilters, setDebouncedFilters] = useState({
    dateRange: defaultRange,
    partnerId: "",
    states: [] as PayoutState[],
    offset: 0,
  });

  useEffect(() => {
    const handler = window.setTimeout(() => {
      setDebouncedFilters({ dateRange, partnerId, states, offset });
    }, 400);
    return () => window.clearTimeout(handler);
  }, [dateRange, partnerId, states, offset]);

  const filters = useMemo(
    () => ({
      date_from: debouncedFilters.dateRange.from,
      date_to: debouncedFilters.dateRange.to,
      partner_id: debouncedFilters.partnerId || undefined,
      state: debouncedFilters.states.length ? debouncedFilters.states : undefined,
      limit,
      offset: debouncedFilters.offset,
      sort: "created_at:desc",
    }),
    [debouncedFilters, limit],
  );

  const { data, isFetching, isLoading, error, refetch } = useQuery({
    queryKey: ["payouts", filters],
    queryFn: () => fetchPayoutBatches(filters),
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  const toggleState = (state: PayoutState) => {
    setOffset(0);
    setStates((prev) => (prev.includes(state) ? prev.filter((s) => s !== state) : [...prev, state]));
  };

  const columns: Column<PayoutBatchSummary>[] = [
    {
      key: "batch_id",
      title: "Batch ID",
      render: (row) => (
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span title={row.batch_id}>{row.batch_id.slice(0, 8)}</span>
          <CopyButton value={row.batch_id} label="Copy" onCopy={() => showToast("success", "Batch ID copied")} />
        </div>
      ),
    },
    { key: "state", title: "State", render: (row) => <PayoutStateBadge state={row.state} /> },
    { key: "total_amount", title: "Total amount", render: (row) => formatRub(row.total_amount) },
    { key: "total_qty", title: "Total qty", render: (row) => row.total_qty },
    { key: "operations_count", title: "Operations", render: (row) => row.operations_count },
    { key: "items_count", title: "Items", render: (row) => row.items_count },
    {
      key: "actions",
      title: "Actions",
      render: (row) => (
        <div style={{ display: "flex", gap: 8 }}>
          <button type="button" className="ghost" onClick={() => navigate(`/finance/payouts/${row.batch_id}`)}>
            View
          </button>
          <button
            type="button"
            className="ghost"
            onClick={() => navigate(`/finance/payouts/${row.batch_id}`)}
            disabled={row.state !== "READY"}
          >
            Mark sent
          </button>
          <button
            type="button"
            className="ghost"
            onClick={() => navigate(`/finance/payouts/${row.batch_id}`)}
            disabled={row.state !== "SENT"}
          >
            Mark settled
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="stack">
      <div className="page-header">
        <h1>Payouts</h1>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button type="button" className="ghost" onClick={() => refetch()}>
            Refresh
          </button>
          {(isLoading || isFetching) && <Loader label="Loading payouts" />}
        </div>
      </div>

      <Suspense fallback={<Loader label="Loading filters" />}>
        <div className="card" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div className="filters">
            <DateRangeFilter
              label="Date range"
              from={dateRange.from}
              to={dateRange.to}
              onChange={(range) => {
                setOffset(0);
                setDateRange(range);
              }}
            />
            <div className="filter">
              <span className="label">Partner</span>
              <input
                placeholder="partner_id"
                value={partnerId}
                onChange={(e) => {
                  setOffset(0);
                  setPartnerId(e.target.value);
                }}
              />
            </div>
            <div className="filter">
              <span className="label">State</span>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {ALL_STATES.map((state) => (
                  <label key={state} style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    <input type="checkbox" checked={states.includes(state)} onChange={() => toggleState(state)} />
                    {state}
                  </label>
                ))}
              </div>
            </div>
          </div>
          <div className="pill-list">
            {QUICK_PRESETS.map((preset) => (
              <button
                key={preset.label}
                type="button"
                className="ghost"
                onClick={() => {
                  setOffset(0);
                  setDateRange(preset.range);
                }}
              >
                {preset.label}
              </button>
            ))}
            <button
              type="button"
              className="ghost"
              onClick={() => {
                setOffset(0);
                setStates(["READY"]);
              }}
            >
              Ready only
            </button>
          </div>
        </div>
      </Suspense>

      {error && (
        <div className="card" style={{ borderColor: "#fecaca" }}>
          <p style={{ color: "#dc2626", fontWeight: 600 }}>Failed to load payouts</p>
          <p style={{ color: "#475569" }}>{error.message}</p>
          <button type="button" className="ghost" onClick={() => refetch()}>
            Retry
          </button>
        </div>
      )}

      {!error && !isLoading && items.length === 0 && <div className="card">No payouts found</div>}

      <Table columns={columns} data={items} onRowClick={(row) => navigate(`/finance/payouts/${row.batch_id}`)} />

      <Pagination total={total} limit={limit} offset={offset} onChange={setOffset} />
      <Toast toast={toast} />
    </div>
  );
};

export default PayoutsList;
