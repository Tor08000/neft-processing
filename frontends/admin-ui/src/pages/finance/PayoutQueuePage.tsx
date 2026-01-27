import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchPayoutQueue } from "../../api/finance";
import type { PayoutQueueItem } from "../../types/payouts";
import { Table, type Column } from "../../components/Table/Table";
import { Pagination } from "../../components/Pagination/Pagination";
import { Loader } from "../../components/Loader/Loader";
import { extractRequestId } from "../ops/opsUtils";
import { CopyButton } from "../../components/CopyButton/CopyButton";

export const PayoutQueuePage: React.FC = () => {
  const navigate = useNavigate();
  const [limit] = useState(50);
  const [offset, setOffset] = useState(0);
  const [status, setStatus] = useState("");
  const [blocked, setBlocked] = useState<"" | "yes" | "no">("");
  const [partner, setPartner] = useState("");
  const [debouncedFilters, setDebouncedFilters] = useState({
    status: "",
    blocked: "",
    partner: "",
    offset: 0,
  });

  useEffect(() => {
    const handler = window.setTimeout(() => {
      setDebouncedFilters({ status, blocked, partner, offset });
    }, 400);
    return () => window.clearTimeout(handler);
  }, [status, blocked, partner, offset]);

  const filters = useMemo(
    () => ({
      status: debouncedFilters.status || undefined,
      blocked: debouncedFilters.blocked === "yes" ? true : debouncedFilters.blocked === "no" ? false : undefined,
      partner: debouncedFilters.partner || undefined,
      limit,
      offset: debouncedFilters.offset,
    }),
    [debouncedFilters, limit],
  );

  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ["payout-queue", filters],
    queryFn: () => fetchPayoutQueue(filters),
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  const columns: Column<PayoutQueueItem>[] = [
    { key: "payout_id", title: "Payout ID", render: (row) => row.payout_id },
    { key: "partner_org", title: "Partner", render: (row) => row.partner_org },
    {
      key: "net_amount",
      title: "Net amount",
      render: (row) => `${row.net_amount ?? row.amount} ${row.currency}`,
    },
    { key: "status", title: "Status", render: (row) => row.status },
    { key: "blocked_reason", title: "Blocked reason", render: (row) => row.blocked_reason ?? row.blockers?.join(", ") ?? "—" },
    {
      key: "correlation",
      title: "Correlation",
      render: (row) =>
        row.correlation_id ? (
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <Link to={`/audit?correlation_id=${encodeURIComponent(row.correlation_id)}`}>Open</Link>
            <CopyButton value={row.correlation_id} label="Copy" />
          </div>
        ) : (
          "—"
        ),
    },
    { key: "created_at", title: "Created", render: (row) => row.created_at ?? "—" },
  ];

  return (
    <div className="stack">
      <div className="page-header">
        <h1>Payout queue</h1>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button type="button" className="ghost" onClick={() => refetch()}>
            Refresh
          </button>
          {(isLoading || isFetching) && <Loader label="Loading payouts" />}
        </div>
      </div>

      <div className="card" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div className="filters">
          <div className="filter">
            <span className="label">Status</span>
            <input value={status} onChange={(event) => setStatus(event.target.value)} placeholder="status" />
          </div>
          <div className="filter">
            <span className="label">Blocked</span>
            <select value={blocked} onChange={(event) => setBlocked(event.target.value as "" | "yes" | "no")}>
              <option value="">All</option>
              <option value="yes">Blocked</option>
              <option value="no">Unblocked</option>
            </select>
          </div>
          <div className="filter">
            <span className="label">Partner</span>
            <input value={partner} onChange={(event) => setPartner(event.target.value)} placeholder="partner id/name" />
          </div>
        </div>
      </div>

      {error ? (
        <div style={{ color: "#dc2626" }}>
          {(error as Error).message}
          {extractRequestId(error) ? <div style={{ marginTop: 4 }}>Request ID: {extractRequestId(error)}</div> : null}
        </div>
      ) : null}

      <Table columns={columns} data={items} loading={isLoading} onRowClick={(row) => navigate(`/finance/payouts/${row.payout_id}`)} />

      <Pagination total={total} limit={limit} offset={offset} onChange={(value) => setOffset(value)} />
    </div>
  );
};

export default PayoutQueuePage;
