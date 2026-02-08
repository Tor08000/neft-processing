import React, { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { fetchModerationQueue } from "../../api/marketplaceModeration";
import type {
  MarketplaceModerationEntityType,
  MarketplaceModerationQueueItem,
  MarketplaceModerationStatus,
} from "../../types/marketplaceModeration";
import { Table, type Column } from "../../components/Table/Table";
import { Pagination } from "../../components/Pagination/Pagination";
import { formatDateTime } from "../../utils/format";
import { Loader } from "../../components/Loader/Loader";

const typeOptions: Array<{ value: MarketplaceModerationEntityType; label: string }> = [
  { value: "PRODUCT", label: "Product" },
  { value: "SERVICE", label: "Service" },
  { value: "OFFER", label: "Offer" },
];

const statusOptions: MarketplaceModerationStatus[] = [
  "PENDING_REVIEW",
  "DRAFT",
  "ACTIVE",
  "SUSPENDED",
  "ARCHIVED",
];

const typeBadgeStyles: Record<MarketplaceModerationEntityType, React.CSSProperties> = {
  PRODUCT: { background: "#e0f2fe", color: "#0369a1" },
  SERVICE: { background: "#fef9c3", color: "#a16207" },
  OFFER: { background: "#ede9fe", color: "#6d28d9" },
};

export const MarketplaceModerationPage: React.FC = () => {
  const navigate = useNavigate();
  const [type, setType] = useState<MarketplaceModerationEntityType | "">("");
  const [status, setStatus] = useState<MarketplaceModerationStatus>("PENDING_REVIEW");
  const [q, setQ] = useState("");
  const [limit, setLimit] = useState(20);
  const [offset, setOffset] = useState(0);

  const queryParams = useMemo(
    () => ({
      type: type || undefined,
      status,
      q: q || undefined,
      limit,
      offset,
    }),
    [type, status, q, limit, offset],
  );

  const { data, isLoading, error, isFetching } = useQuery({
    queryKey: ["marketplaceModerationQueue", queryParams],
    queryFn: () => fetchModerationQueue(queryParams),
    staleTime: 15_000,
    placeholderData: (previousData) => previousData,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  const columns: Column<MarketplaceModerationQueueItem>[] = [
    {
      key: "type",
      title: "Type",
      render: (row) => (
        <span
          style={{
            ...typeBadgeStyles[row.type],
            padding: "2px 8px",
            borderRadius: 999,
            fontSize: 12,
            fontWeight: 600,
          }}
        >
          {row.type}
        </span>
      ),
    },
    { key: "title", title: "Title", render: (row) => row.title },
    { key: "partner", title: "Partner", render: (row) => row.partner_id },
    { key: "status", title: "Status", render: (row) => row.status },
    {
      key: "submitted_at",
      title: "Submitted",
      render: (row) => (row.submitted_at ? formatDateTime(row.submitted_at) : "—"),
    },
    {
      key: "actions",
      title: "Actions",
      render: (row) => (
        <button
          type="button"
          className="neft-btn-secondary"
          onClick={(event) => {
            event.stopPropagation();
            const path =
              row.type === "PRODUCT"
                ? `/marketplace/moderation/product/${row.id}`
                : row.type === "SERVICE"
                  ? `/marketplace/moderation/service/${row.id}`
                  : `/marketplace/moderation/offer/${row.id}`;
            navigate(path);
          }}
        >
          Open
        </button>
      ),
    },
  ];

  return (
    <div>
      <div className="page-header">
        <h1>Marketplace → Moderation</h1>
        {(isLoading || isFetching) && <Loader label="Обновляем очередь" />}
        {error && <span style={{ color: "#dc2626" }}>{error.message}</span>}
      </div>

      <div className="filters" style={{ alignItems: "flex-end" }}>
        <div className="filter">
          <span className="label">Type</span>
          <select
            value={type}
            onChange={(event) => {
              setType(event.target.value as MarketplaceModerationEntityType | "");
              setOffset(0);
            }}
          >
            <option value="">All</option>
            {typeOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div className="filter">
          <span className="label">Status</span>
          <select
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as MarketplaceModerationStatus);
              setOffset(0);
            }}
          >
            {statusOptions.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>
        <div className="filter" style={{ minWidth: 220 }}>
          <span className="label">Search</span>
          <input
            value={q}
            onChange={(event) => {
              setQ(event.target.value);
              setOffset(0);
            }}
            placeholder="Title"
          />
        </div>
        <div className="filter">
          <span className="label">Limit</span>
          <select
            value={limit}
            onChange={(event) => {
              setLimit(Number(event.target.value));
              setOffset(0);
            }}
          >
            {[10, 20, 50].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>
      </div>

      <Table columns={columns} data={items} loading={isLoading} emptyMessage="Очередь модерации пуста" />

      <div style={{ marginTop: 12 }}>
        <Pagination total={total} limit={limit} offset={offset} onChange={setOffset} />
      </div>
    </div>
  );
};

export default MarketplaceModerationPage;
