import React, { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { fetchModerationQueue } from "../../api/marketplaceModeration";
import type {
  MarketplaceModerationEntityType,
  MarketplaceModerationQueueItem,
} from "../../types/marketplaceModeration";
import { Table, type Column } from "../../components/Table/Table";
import { Pagination } from "../../components/Pagination/Pagination";
import { formatDateTime } from "../../utils/format";
import { Loader } from "../../components/Loader/Loader";
import { describeRuntimeError } from "../../api/runtimeError";
import {
  moderationQueueCopy,
  moderationStatusOptions,
  moderationTypeOptions,
} from "./marketplaceModerationCopy";

const typeBadgeStyles: Record<MarketplaceModerationEntityType, React.CSSProperties> = {
  PRODUCT: { background: "#e0f2fe", color: "#0369a1" },
  SERVICE: { background: "#fef9c3", color: "#a16207" },
  OFFER: { background: "#ede9fe", color: "#6d28d9" },
};

export const MarketplaceModerationPage: React.FC = () => {
  const navigate = useNavigate();
  const [type, setType] = useState<MarketplaceModerationEntityType | "">("");
  const [status, setStatus] = useState(moderationQueueCopy.defaults.status);
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

  const { data, isLoading, error, isFetching, refetch } = useQuery({
    queryKey: ["marketplaceModerationQueue", queryParams],
    queryFn: () => fetchModerationQueue(queryParams),
    staleTime: 15_000,
    placeholderData: (previousData) => previousData,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const filtersActive = Boolean(type || q.trim() || status !== moderationQueueCopy.defaults.status);
  const queueError = error
    ? describeRuntimeError(
        error,
        "Moderation queue owner route returned an internal error. Retry or inspect request metadata below.",
      )
    : null;

  const columns: Column<MarketplaceModerationQueueItem>[] = [
    {
      key: "type",
      title: moderationQueueCopy.columns.type,
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
    { key: "title", title: moderationQueueCopy.columns.title, render: (row) => row.title },
    { key: "partner", title: moderationQueueCopy.columns.partner, render: (row) => row.partner_id },
    { key: "status", title: moderationQueueCopy.columns.status, render: (row) => row.status },
    {
      key: "submitted_at",
      title: moderationQueueCopy.columns.submitted,
      render: (row) => (row.submitted_at ? formatDateTime(row.submitted_at) : "—"),
    },
    {
      key: "actions",
      title: moderationQueueCopy.columns.actions,
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
          {moderationQueueCopy.actions.open}
        </button>
      ),
    },
  ];

  const footer = (
    <div
      className="table-footer__content"
      style={{ justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}
    >
      <span className="muted">{moderationQueueCopy.footer.rows(items.length, total)}</span>
      <Pagination
        total={total}
        limit={limit}
        offset={offset}
        onChange={setOffset}
        labels={{
          previous: moderationQueueCopy.pagination.previous,
          next: moderationQueueCopy.pagination.next,
          summary: moderationQueueCopy.pagination.summary,
        }}
      />
    </div>
  );

  return (
    <div>
      <div className="page-header">
        <div>
          <h1>{moderationQueueCopy.header.title}</h1>
          <p className="muted">{moderationQueueCopy.header.subtitle}</p>
        </div>
        {isFetching && !isLoading ? <Loader label={moderationQueueCopy.loadingLabel} /> : null}
      </div>

      <Table
        columns={columns}
        data={items}
        loading={isLoading && !data}
        toolbar={
          <div className="table-toolbar">
            <div className="filters" style={{ alignItems: "flex-end" }}>
              <div className="filter">
                <label className="label" htmlFor="moderation-type-filter">
                  {moderationQueueCopy.filters.type}
                </label>
                <select
                  id="moderation-type-filter"
                  value={type}
                  onChange={(event) => {
                    setType(event.target.value as MarketplaceModerationEntityType | "");
                    setOffset(0);
                  }}
                >
                  <option value="">{moderationQueueCopy.filters.allTypes}</option>
                  {moderationTypeOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="filter">
                <label className="label" htmlFor="moderation-status-filter">
                  {moderationQueueCopy.filters.status}
                </label>
                <select
                  id="moderation-status-filter"
                  value={status}
                  onChange={(event) => {
                    setStatus(event.target.value as typeof status);
                    setOffset(0);
                  }}
                >
                  {moderationStatusOptions.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </div>
              <div className="filter" style={{ minWidth: 220 }}>
                <label className="label" htmlFor="moderation-search-filter">
                  {moderationQueueCopy.filters.search}
                </label>
                <input
                  id="moderation-search-filter"
                  value={q}
                  onChange={(event) => {
                    setQ(event.target.value);
                    setOffset(0);
                  }}
                  placeholder={moderationQueueCopy.filters.searchPlaceholder}
                />
              </div>
              <div className="filter">
                <label className="label" htmlFor="moderation-limit-filter">
                  {moderationQueueCopy.filters.limit}
                </label>
                <select
                  id="moderation-limit-filter"
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
            <div className="toolbar-actions">
              {filtersActive && items.length > 0 ? (
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => {
                    setType("");
                    setStatus(moderationQueueCopy.defaults.status);
                    setQ("");
                    setOffset(0);
                  }}
                >
                  {moderationQueueCopy.actions.reset}
                </button>
              ) : null}
            </div>
          </div>
        }
        errorState={
          queueError
            ? {
                title: moderationQueueCopy.errors.title,
                description: queueError.description,
                actionLabel: moderationQueueCopy.actions.retry,
                actionOnClick: () => {
                  void refetch();
                },
                details: queueError.details,
                requestId: queueError.requestId,
                correlationId: queueError.correlationId,
              }
            : undefined
        }
        emptyState={{
          title: filtersActive ? moderationQueueCopy.empty.filteredTitle : moderationQueueCopy.empty.pristineTitle,
          description: filtersActive
            ? moderationQueueCopy.empty.filteredDescription
            : moderationQueueCopy.empty.pristineDescription,
          actionLabel: filtersActive ? moderationQueueCopy.actions.reset : undefined,
          actionOnClick: filtersActive
            ? () => {
                setType("");
                setStatus(moderationQueueCopy.defaults.status);
                setQ("");
                setOffset(0);
              }
            : undefined,
        }}
        footer={footer}
      />
    </div>
  );
};

export default MarketplaceModerationPage;
