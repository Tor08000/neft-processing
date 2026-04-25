import React, { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { fetchAuditCorrelation, fetchAuditFeed } from "../../api/audit";
import { ApiError } from "../../api/http";
import { useAuth } from "../../auth/AuthContext";
import { CopyButton } from "../../components/CopyButton/CopyButton";
import { EmptyState } from "../../components/common/EmptyState";
import { ErrorState } from "../../components/common/ErrorState";
import { JsonViewer } from "../../components/common/JsonViewer";
import { Loader } from "../../components/Loader/Loader";
import type { AuditEvent } from "../../types/audit";
import { AdminMisconfigPage } from "./AdminStatusPages";

const FILTERS = [
  { key: "money", label: "money" },
  { key: "legal", label: "legal" },
  { key: "override", label: "override" },
  { key: "auth", label: "auth" },
];

const EMPTY_VALUE = "-";

const renderTitle = (event: AuditEvent) =>
  event.title ?? event.action ?? event.type ?? event.id ?? "Audit event";

const isAdminUserEvent = (event: AuditEvent) => event.entity_type === "admin_user" && Boolean(event.entity_id);

export const AuditPage: React.FC = () => {
  const { accessToken } = useAuth();
  const params = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [query, setQuery] = useState(searchParams.get("search") ?? "");
  const [correlation, setCorrelation] = useState(
    params.correlationId ?? searchParams.get("correlation_id") ?? "",
  );
  const [activeFilters, setActiveFilters] = useState<string[]>(
    searchParams.get("type")?.split(",").filter(Boolean) ?? [],
  );
  const [scope, setScope] = useState(searchParams.get("scope") ?? "");
  const [actorType, setActorType] = useState(searchParams.get("actor_type") ?? "");
  const [entityType, setEntityType] = useState(searchParams.get("entity_type") ?? "");
  const [entityId, setEntityId] = useState(searchParams.get("entity_id") ?? "");
  const [fromDate, setFromDate] = useState(searchParams.get("from") ?? "");
  const [toDate, setToDate] = useState(searchParams.get("to") ?? "");

  useEffect(() => {
    if (params.correlationId && params.correlationId !== correlation) {
      setCorrelation(params.correlationId);
    }
  }, [params.correlationId, correlation]);

  useEffect(() => {
    const nextFilters = searchParams.get("type")?.split(",").filter(Boolean) ?? [];
    const currentFilters = [...activeFilters].sort().join(",");
    const resolvedFilters = [...nextFilters].sort().join(",");
    const nextQuery = searchParams.get("search") ?? "";
    const nextCorrelation = params.correlationId ?? searchParams.get("correlation_id") ?? "";
    const nextScope = searchParams.get("scope") ?? "";
    const nextActorType = searchParams.get("actor_type") ?? "";
    const nextEntityType = searchParams.get("entity_type") ?? "";
    const nextEntityId = searchParams.get("entity_id") ?? "";
    const nextFrom = searchParams.get("from") ?? "";
    const nextTo = searchParams.get("to") ?? "";

    if (query !== nextQuery) setQuery(nextQuery);
    if (correlation !== nextCorrelation) setCorrelation(nextCorrelation);
    if (currentFilters !== resolvedFilters) setActiveFilters(nextFilters);
    if (scope !== nextScope) setScope(nextScope);
    if (actorType !== nextActorType) setActorType(nextActorType);
    if (entityType !== nextEntityType) setEntityType(nextEntityType);
    if (entityId !== nextEntityId) setEntityId(nextEntityId);
    if (fromDate !== nextFrom) setFromDate(nextFrom);
    if (toDate !== nextTo) setToDate(nextTo);
  }, [
    searchParams,
    params.correlationId,
    query,
    correlation,
    activeFilters,
    scope,
    actorType,
    entityType,
    entityId,
    fromDate,
    toDate,
  ]);

  const filters = useMemo(
    () => ({
      type: activeFilters.length ? activeFilters.join(",") : undefined,
      search: query || undefined,
      correlation_id: correlation || undefined,
      scope: scope || undefined,
      actor_type: actorType || undefined,
      entity_type: entityType || undefined,
      entity_id: entityId || undefined,
      from: fromDate || undefined,
      to: toDate || undefined,
    }),
    [activeFilters, query, correlation, scope, actorType, entityType, entityId, fromDate, toDate],
  );
  const hasFilters = Boolean(
    activeFilters.length || query || correlation || scope || actorType || entityType || entityId || fromDate || toDate,
  );

  const {
    data,
    isLoading,
    isFetching,
    error: feedError,
    refetch,
  } = useQuery({
    queryKey: ["audit-feed", filters],
    queryFn: () => fetchAuditFeed(accessToken ?? "", filters),
    enabled: Boolean(accessToken),
    staleTime: 20_000,
    placeholderData: (prev) => prev,
  });

  const { data: chainData, isLoading: chainLoading } = useQuery({
    queryKey: ["audit-correlation", correlation],
    queryFn: () => fetchAuditCorrelation(accessToken ?? "", correlation),
    enabled: Boolean(accessToken && correlation),
  });

  const events = data?.items ?? [];

  const toggleFilter = (key: string) => {
    setActiveFilters((prev) => (prev.includes(key) ? prev.filter((item) => item !== key) : [...prev, key]));
  };

  const applyFilters = () => {
    const next = new URLSearchParams();
    if (query) next.set("search", query);
    if (correlation) next.set("correlation_id", correlation);
    if (activeFilters.length) next.set("type", activeFilters.join(","));
    if (scope) next.set("scope", scope);
    if (actorType) next.set("actor_type", actorType);
    if (entityType) next.set("entity_type", entityType);
    if (entityId) next.set("entity_id", entityId);
    if (fromDate) next.set("from", fromDate);
    if (toDate) next.set("to", toDate);
    setSearchParams(next);
    refetch();
  };

  const chainEvents = chainData?.items ?? chainData?.events ?? [];
  const adminProfilePath = entityType === "admin_user" && entityId ? `/admins/${encodeURIComponent(entityId)}` : null;

  if (feedError instanceof ApiError && feedError.status === 404) {
    return <AdminMisconfigPage requestId={feedError.requestId ?? undefined} errorId={feedError.errorCode ?? undefined} />;
  }

  return (
    <div className="stack">
      <div className="page-header">
        <h1>Audit</h1>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button type="button" className="ghost" onClick={() => refetch()}>
            Refresh
          </button>
          {(isLoading || isFetching) && <Loader label="Loading audit" />}
        </div>
      </div>

      <div className="card audit-controls">
        <div className="audit-controls__filters">
          {FILTERS.map((filter) => (
            <label className="checkbox audit-filter" key={filter.key}>
              <input
                type="checkbox"
                checked={activeFilters.includes(filter.key)}
                onChange={() => toggleFilter(filter.key)}
              />
              <span>{filter.label}</span>
            </label>
          ))}
        </div>
        <div className="audit-controls__search">
          <input
            type="text"
            placeholder="Search (actor, entity, action)"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <input
            type="text"
            placeholder="Scope"
            value={scope}
            onChange={(event) => setScope(event.target.value)}
          />
          <input
            type="text"
            placeholder="Actor type"
            value={actorType}
            onChange={(event) => setActorType(event.target.value)}
          />
          <input
            type="text"
            placeholder="Entity type"
            value={entityType}
            onChange={(event) => setEntityType(event.target.value)}
          />
          <input
            type="text"
            placeholder="Entity ID"
            value={entityId}
            onChange={(event) => setEntityId(event.target.value)}
          />
          <input
            type="text"
            placeholder="Correlation ID"
            value={correlation}
            onChange={(event) => setCorrelation(event.target.value)}
          />
          <input type="date" value={fromDate} onChange={(event) => setFromDate(event.target.value)} />
          <input type="date" value={toDate} onChange={(event) => setToDate(event.target.value)} />
          <button type="button" className="ghost" onClick={applyFilters}>
            Apply
          </button>
        </div>
      </div>

      {entityType || entityId ? (
        <div className="card" style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <strong>Scoped audit view</strong>
          {entityType ? <span className="neft-chip neft-chip-muted">entity_type={entityType}</span> : null}
          {entityId ? <span className="neft-chip neft-chip-muted">entity_id={entityId}</span> : null}
          {adminProfilePath ? <Link to={adminProfilePath}>Open admin profile</Link> : null}
        </div>
      ) : null}

      <div className="audit-timeline">
        {feedError ? (
          <ErrorState
            title="Failed to load audit feed"
            description={feedError instanceof Error ? feedError.message : "Retry the audit query to restore the operator trail."}
            actionLabel="Retry"
            onAction={() => void refetch()}
            requestId={feedError instanceof ApiError ? feedError.requestId : null}
            correlationId={feedError instanceof ApiError ? feedError.correlationId : null}
          />
        ) : events.length === 0 ? (
          <EmptyState
            title={hasFilters ? "Audit events not found" : "No audit events yet"}
            description={
              hasFilters
                ? "Adjust the audit filters or refresh the feed to inspect a different operator slice."
                : "The canonical audit trail is mounted, but there are no events in the current operator window yet."
            }
            primaryAction={{ label: "Refresh", onClick: () => void refetch() }}
          />
        ) : (
          events.map((event) => (
            <div className="audit-item" key={`${event.id ?? event.ts ?? "event"}-${event.correlation_id ?? ""}`}>
              <div className="audit-item__marker">
                <span className="audit-item__icon">+</span>
              </div>
              <div className="audit-item__content">
                <div className="audit-item__header">
                  <div className="audit-item__title">{renderTitle(event)}</div>
                  <div className="audit-item__meta">
                    <span>{event.ts ?? EMPTY_VALUE}</span>
                    {event.actor ? <span>| {event.actor}</span> : null}
                  </div>
                </div>
                {event.reason ? <div className="audit-item__reason">Reason: {event.reason}</div> : null}
                {event.entity_type || event.entity_id ? (
                  <div
                    className="audit-item__meta"
                    style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}
                  >
                    <span>{[event.entity_type, event.entity_id].filter(Boolean).join(":") || "entity"}</span>
                    {isAdminUserEvent(event) ? (
                      <Link to={`/admins/${encodeURIComponent(event.entity_id ?? "")}`}>Admin profile</Link>
                    ) : null}
                    {event.entity_type && event.entity_id ? (
                      <Link
                        to={`/audit?entity_type=${encodeURIComponent(event.entity_type)}&entity_id=${encodeURIComponent(
                          event.entity_id,
                        )}`}
                      >
                        Filter entity
                      </Link>
                    ) : null}
                  </div>
                ) : null}
                {event.correlation_id ? (
                  <div className="audit-item__meta" style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <span>{event.correlation_id}</span>
                    <CopyButton value={event.correlation_id} label="Copy" />
                    <button type="button" className="ghost" onClick={() => setCorrelation(event.correlation_id ?? "")}>
                      Drilldown
                    </button>
                  </div>
                ) : null}
              </div>
            </div>
          ))
        )}
      </div>

      {correlation ? (
        <div className="card">
          <h2 style={{ marginTop: 0 }}>Correlation chain</h2>
          {chainLoading ? <Loader label="Loading chain" /> : null}
          {chainEvents.length ? (
            <div style={{ display: "grid", gap: 12 }}>
              {chainEvents.map((event) => (
                <div key={event.id ?? event.ts ?? JSON.stringify(event)} className="audit-block">
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <strong>{renderTitle(event)}</strong>
                    {event.ts ? <span className="muted">{event.ts}</span> : null}
                    {isAdminUserEvent(event) ? (
                      <Link to={`/admins/${encodeURIComponent(event.entity_id ?? "")}`}>Admin profile</Link>
                    ) : null}
                  </div>
                  {event.reason ? <div className="audit-item__reason">Reason: {event.reason}</div> : null}
                  {(event.payload || event.meta) ? (
                    <JsonViewer value={event.payload ?? event.meta ?? {}} redactionMode="audit" />
                  ) : null}
                </div>
              ))}
            </div>
          ) : (
            <div className="muted">No chain events.</div>
          )}
        </div>
      ) : null}
    </div>
  );
};

export default AuditPage;
