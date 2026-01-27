import React, { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "react-router-dom";
import { fetchAuditCorrelation, fetchAuditFeed } from "../../api/audit";
import type { AuditEvent } from "../../types/audit";
import { useAuth } from "../../auth/AuthContext";
import { Loader } from "../../components/Loader/Loader";
import { CopyButton } from "../../components/CopyButton/CopyButton";
import { JsonViewer } from "../../components/common/JsonViewer";

const FILTERS = [
  { key: "money", label: "money" },
  { key: "legal", label: "legal" },
  { key: "override", label: "override" },
  { key: "auth", label: "auth" },
];

const renderTitle = (event: AuditEvent) =>
  event.title ?? event.action ?? event.type ?? event.id ?? "Audit event";

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
  const [fromDate, setFromDate] = useState(searchParams.get("from") ?? "");
  const [toDate, setToDate] = useState(searchParams.get("to") ?? "");

  useEffect(() => {
    if (params.correlationId && params.correlationId !== correlation) {
      setCorrelation(params.correlationId);
    }
  }, [params.correlationId, correlation]);

  const filters = useMemo(
    () => ({
      type: activeFilters.length ? activeFilters.join(",") : undefined,
      search: query || undefined,
      correlation_id: correlation || undefined,
      scope: scope || undefined,
      actor_type: actorType || undefined,
      from: fromDate || undefined,
      to: toDate || undefined,
    }),
    [activeFilters, query, correlation, scope, actorType, fromDate, toDate],
  );

  const { data, isLoading, isFetching, refetch } = useQuery({
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
    if (fromDate) next.set("from", fromDate);
    if (toDate) next.set("to", toDate);
    setSearchParams(next);
    refetch();
  };

  const chainEvents = chainData?.items ?? chainData?.events ?? [];

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

      <div className="audit-timeline">
        {events.length === 0 ? (
          <div className="muted">Audit events not found.</div>
        ) : (
          events.map((event) => (
            <div className="audit-item" key={`${event.id ?? event.ts ?? "event"}-${event.correlation_id ?? ""}`}>
              <div className="audit-item__marker">
                <span className="audit-item__icon">◆</span>
              </div>
              <div className="audit-item__content">
                <div className="audit-item__header">
                  <div className="audit-item__title">{renderTitle(event)}</div>
                  <div className="audit-item__meta">
                    <span>{event.ts ?? "—"}</span>
                    {event.actor ? <span>· {event.actor}</span> : null}
                  </div>
                </div>
                {event.reason ? <div className="audit-item__reason">Reason: {event.reason}</div> : null}
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
                  </div>
                  {event.reason ? <div className="audit-item__reason">Reason: {event.reason}</div> : null}
                  {(event.payload || event.meta) && (
                    <JsonViewer value={event.payload ?? event.meta ?? {}} redactionMode="audit" />
                  )}
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
