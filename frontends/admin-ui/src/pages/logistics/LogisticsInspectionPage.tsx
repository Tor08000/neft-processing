import React, { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { fetchLogisticsInspection, recomputeLogisticsEta } from "../../api/logistics";
import { useAuth } from "../../auth/AuthContext";
import { useAdmin } from "../../admin/AdminContext";
import { EmptyState } from "../../components/common/EmptyState";
import { ErrorState } from "../../components/common/ErrorState";
import { Loader } from "../../components/Loader/Loader";
import { logisticsInspectionCopy } from "./logisticsInspectionCopy";

const EMPTY_VALUE = "-";

const formatDateTime = (value?: string | null) => {
  if (!value) return EMPTY_VALUE;
  try {
    return new Date(value).toLocaleString("ru-RU");
  } catch {
    return value;
  }
};

const summarizePayload = (payload: Record<string, unknown>) => JSON.stringify(payload, null, 2);

export const LogisticsInspectionPage: React.FC = () => {
  const { accessToken } = useAuth();
  const { profile } = useAdmin();
  const [searchParams, setSearchParams] = useSearchParams();
  const [draftOrderId, setDraftOrderId] = useState(searchParams.get("order_id") ?? "");
  const [activeOrderId, setActiveOrderId] = useState(searchParams.get("order_id") ?? "");
  const canOperate = Boolean(profile?.permissions.ops?.operate) && !profile?.read_only;

  const inspectionQuery = useQuery({
    queryKey: ["admin-logistics-inspection", activeOrderId],
    queryFn: () => fetchLogisticsInspection(accessToken ?? "", activeOrderId),
    enabled: Boolean(accessToken && activeOrderId),
    staleTime: 30_000,
  });

  const recomputeMutation = useMutation({
    mutationFn: () => recomputeLogisticsEta(accessToken ?? "", activeOrderId),
    onSuccess: () => {
      void inspectionQuery.refetch();
    },
  });

  const inspection = inspectionQuery.data;
  const routeSummary = useMemo(
    () =>
      inspection?.routes.map((route) => ({
        id: route.id,
        label: `v${route.version} | ${route.status}`,
        detail: `${route.distance_km ?? EMPTY_VALUE} km | ${route.planned_duration_minutes ?? EMPTY_VALUE} min`,
      })) ?? [],
    [inspection],
  );

  const applyOrderId = () => {
    const nextOrderId = draftOrderId.trim();
    setActiveOrderId(nextOrderId);
    setSearchParams(nextOrderId ? { order_id: nextOrderId } : {});
  };

  return (
    <div className="stack">
      <div className="page-header">
        <div>
          <h1>Logistics inspection</h1>
          <p className="muted">Canonical admin inspection over order, route, ETA and navigator explain artifacts.</p>
        </div>
      </div>

      <section className="card">
        <div className="surface-toolbar">
          <div className="table-toolbar__content" style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
            <label style={{ display: "grid", gap: 6, minWidth: 260 }}>
              <span className="label">Order ID</span>
              <input
                className="neft-input"
                value={draftOrderId}
                onChange={(event) => setDraftOrderId(event.target.value)}
                placeholder="log-order-123"
              />
            </label>
            <button className="neft-btn-primary" type="button" onClick={applyOrderId}>
              Inspect
            </button>
            <button
              className="neft-btn-secondary"
              type="button"
              disabled={!activeOrderId || !canOperate || recomputeMutation.isPending}
              onClick={() => recomputeMutation.mutate()}
            >
              Recompute ETA
            </button>
            {!canOperate ? <span className="muted">Read-only mode: ETA recompute disabled.</span> : null}
          </div>
        </div>
      </section>

      {!activeOrderId ? (
        <section className="card">
          <EmptyState
            title={logisticsInspectionCopy.firstUse.title}
            description={logisticsInspectionCopy.firstUse.description}
            hint={logisticsInspectionCopy.firstUse.hint}
          />
        </section>
      ) : null}

      {inspectionQuery.isLoading ? (
        <section className="card">
          <Loader label={logisticsInspectionCopy.loadingLabel} />
        </section>
      ) : null}

      {inspectionQuery.error instanceof Error ? (
        <section className="card">
          <ErrorState
            title={logisticsInspectionCopy.unavailable.title}
            description={inspectionQuery.error.message}
            actionLabel={logisticsInspectionCopy.unavailable.actionLabel}
            onAction={() => void inspectionQuery.refetch()}
          />
        </section>
      ) : null}

      {inspection ? (
        <>
          <section className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16 }}>
            <div className="neft-card" style={{ margin: 0 }}>
              <div className="label">Order</div>
              <div style={{ fontWeight: 700 }}>{inspection.order.id}</div>
              <div className="muted">{inspection.order.status}</div>
            </div>
            <div className="neft-card" style={{ margin: 0 }}>
              <div className="label">Client</div>
              <div style={{ fontWeight: 700 }}>{inspection.order.client_id}</div>
              <div className="muted">{inspection.order.order_type}</div>
            </div>
            <div className="neft-card" style={{ margin: 0 }}>
              <div className="label">Routes</div>
              <div style={{ fontWeight: 700 }}>{inspection.routes.length}</div>
              <div className="muted">Active: {inspection.active_route?.id ?? EMPTY_VALUE}</div>
            </div>
            <div className="neft-card" style={{ margin: 0 }}>
              <div className="label">Tracking</div>
              <div style={{ fontWeight: 700 }}>{inspection.tracking_events_count}</div>
              <div className="muted">Explains: {inspection.navigator_explains.length}</div>
            </div>
          </section>

          <section className="neft-card">
            <div className="card__header">
              <div>
                <h2 style={{ fontSize: 20, fontWeight: 700 }}>Order and route truth</h2>
                <p className="muted">Grounded inspection data from the canonical admin logistics owner.</p>
              </div>
            </div>
            <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
              <div>
                <h3 style={{ marginTop: 0 }}>Order</h3>
                <div className="muted">
                  {inspection.order.origin_text ?? EMPTY_VALUE}
                  {" -> "}
                  {inspection.order.destination_text ?? EMPTY_VALUE}
                </div>
                <div className="muted">Planned start: {formatDateTime(inspection.order.planned_start_at)}</div>
                <div className="muted">Planned end: {formatDateTime(inspection.order.planned_end_at)}</div>
                <div className="muted">Vehicle: {inspection.order.vehicle_id ?? EMPTY_VALUE}</div>
                <div className="muted">Driver: {inspection.order.driver_id ?? EMPTY_VALUE}</div>
              </div>
              <div>
                <h3 style={{ marginTop: 0 }}>Route versions</h3>
                {routeSummary.length ? (
                  <ul>
                    {routeSummary.map((route) => (
                      <li key={route.id}>
                        <strong>{route.id}</strong> | {route.label} | {route.detail}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <EmptyState
                    title={logisticsInspectionCopy.routesEmpty.title}
                    description={logisticsInspectionCopy.routesEmpty.description}
                  />
                )}
              </div>
              <div>
                <h3 style={{ marginTop: 0 }}>Latest ETA</h3>
                {inspection.latest_eta_snapshot ? (
                  <>
                    <div className="muted">Method: {inspection.latest_eta_snapshot.method}</div>
                    <div className="muted">ETA end: {formatDateTime(inspection.latest_eta_snapshot.eta_end_at)}</div>
                    <div className="muted">Confidence: {inspection.latest_eta_snapshot.eta_confidence}</div>
                    <div className="muted">Computed: {formatDateTime(inspection.latest_eta_snapshot.computed_at)}</div>
                  </>
                ) : (
                  <EmptyState title={logisticsInspectionCopy.etaEmpty.title} description={logisticsInspectionCopy.etaEmpty.description} />
                )}
              </div>
            </div>
          </section>

          <section className="grid" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
            <div className="neft-card" style={{ margin: 0 }}>
              <h3 style={{ marginTop: 0 }}>Active route stops</h3>
              {inspection.active_route_stops.length ? (
                <ol>
                  {inspection.active_route_stops.map((stop) => (
                    <li key={stop.id}>
                      <strong>{stop.name ?? stop.stop_type}</strong> | {stop.status}
                    </li>
                  ))}
                </ol>
              ) : (
                <EmptyState
                  title={logisticsInspectionCopy.stopsEmpty.title}
                  description={logisticsInspectionCopy.stopsEmpty.description}
                />
              )}
            </div>
            <div className="neft-card" style={{ margin: 0 }}>
              <h3 style={{ marginTop: 0 }}>Navigator snapshot</h3>
              {inspection.latest_route_snapshot ? (
                <>
                  <div className="muted">Provider: {inspection.latest_route_snapshot.provider}</div>
                  <div className="muted">Distance: {inspection.latest_route_snapshot.distance_km} km</div>
                  <div className="muted">ETA: {inspection.latest_route_snapshot.eta_minutes ?? EMPTY_VALUE} min</div>
                  <div className="muted">Captured: {formatDateTime(inspection.latest_route_snapshot.created_at)}</div>
                </>
              ) : (
                <EmptyState
                  title={logisticsInspectionCopy.navigatorEmpty.title}
                  description={logisticsInspectionCopy.navigatorEmpty.description}
                />
              )}
            </div>
            <div className="neft-card" style={{ margin: 0 }}>
              <h3 style={{ marginTop: 0 }}>Tracking tail</h3>
              {inspection.last_tracking_event ? (
                <>
                  <div className="muted">Last event: {inspection.last_tracking_event.event_type}</div>
                  <div className="muted">At: {formatDateTime(inspection.last_tracking_event.ts)}</div>
                  <div className="muted">Vehicle: {inspection.last_tracking_event.vehicle_id ?? EMPTY_VALUE}</div>
                </>
              ) : (
                <EmptyState
                  title={logisticsInspectionCopy.trackingEmpty.title}
                  description={logisticsInspectionCopy.trackingEmpty.description}
                />
              )}
            </div>
          </section>

          <section className="neft-card">
            <div className="card__header">
              <div>
                <h2 style={{ fontSize: 20, fontWeight: 700 }}>Explain artifacts</h2>
                <p className="muted">Stored navigator explain payloads without synthetic drilldown wrappers.</p>
              </div>
              <Link to={`/geo?order_id=${inspection.order.id}`}>Open Geo analytics</Link>
            </div>
            {inspection.navigator_explains.length ? (
              <div className="stack">
                {inspection.navigator_explains.map((explain) => (
                  <div key={explain.id} className="neft-card" style={{ margin: 0 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
                      <strong>{explain.type}</strong>
                      <span className="muted">{formatDateTime(explain.created_at)}</span>
                    </div>
                    <pre className="neft-pre" style={{ marginTop: 12 }}>
                      {summarizePayload(explain.payload)}
                    </pre>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                title={logisticsInspectionCopy.explainEmpty.title}
                description={logisticsInspectionCopy.explainEmpty.description}
              />
            )}
          </section>
        </>
      ) : null}
    </div>
  );
};

export default LogisticsInspectionPage;
