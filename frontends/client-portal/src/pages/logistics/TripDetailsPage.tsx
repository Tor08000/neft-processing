import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { useI18n } from "../../i18n";
import {
  fetchTripById,
  fetchTripDeviations,
  fetchTripEta,
  fetchTripPosition,
  fetchTripRoute,
  fetchTripSlaImpact,
  fetchTripTracking,
  fetchTripFuel,
} from "../../api/logistics";
import type {
  RouteDetail,
  TripDetail,
  TripDeviationEvent,
  TripDeviationSeverity,
  TripDeviationType,
  TripDeviationsResponse,
  TripEta,
  TripSlaImpact,
  TripStatus,
  TripStop,
  TripTrackingPoint,
  TripTrackingResponse,
  TripFuelResponse,
} from "../../types/logistics";
import { StatusBadge } from "../../components/StatusBadge";
import type { Column } from "../../components/common/Table";
import { Table } from "../../components/common/Table";
import { AppErrorState, AppForbiddenState, AppLoadingState, AppEmptyState } from "../../components/states";
import { ModuleUnavailablePage } from "../ModuleUnavailablePage";
import { ApiError } from "../../api/http";
import { formatDateTime } from "../../utils/format";

const statusSteps: TripStatus[] = ["CREATED", "IN_PROGRESS", "COMPLETED"];
const TRACKING_LIMIT = 200;
const DEVIATIONS_LIMIT = 200;
const DEVIATIONS_POLL_INTERVAL_MS = 30000;
const FUEL_POLL_INTERVAL_MS = 60000;

const isModuleDisabledError = (error: ApiError) => {
  const code = error.errorCode ?? "";
  return code.includes("module_disabled") || error.message.includes("module_disabled");
};

const formatMeta = (meta?: Record<string, unknown> | null) => JSON.stringify(meta ?? {}, null, 2);

const formatDateValue = (value: string | null | undefined, fallback: string) =>
  value ? formatDateTime(value) : fallback;

type TrackingWindow = "30m" | "2h" | "24h";

const windowToMs: Record<TrackingWindow, number> = {
  "30m": 30 * 60 * 1000,
  "2h": 2 * 60 * 60 * 1000,
  "24h": 24 * 60 * 60 * 1000,
};

const asTripTrackingPoint = (value: unknown): TripTrackingPoint | null => {
  if (!value || typeof value !== "object") return null;
  const point = value as Record<string, unknown>;
  if (typeof point.ts !== "string" || typeof point.lat !== "number" || typeof point.lon !== "number") return null;
  return {
    ts: point.ts,
    lat: point.lat,
    lon: point.lon,
    speed_kmh: typeof point.speed_kmh === "number" ? point.speed_kmh : null,
    heading: typeof point.heading === "number" ? point.heading : null,
    source: point.source === "manual" ? "manual" : "gps",
    accuracy_m: typeof point.accuracy_m === "number" ? point.accuracy_m : null,
  };
};

const normalizeTrackingResponse = (tripId: string, value: unknown): TripTrackingResponse => {
  if (Array.isArray(value)) {
    const items = value.map((item) => asTripTrackingPoint(item)).filter((item): item is TripTrackingPoint => Boolean(item));
    return {
      trip_id: tripId,
      items,
      last: items.length ? items[items.length - 1] : null,
    };
  }
  const payload = value as Partial<TripTrackingResponse> | null;
  const itemsRaw = Array.isArray(payload?.items) ? payload.items : [];
  const items = itemsRaw.map((item) => asTripTrackingPoint(item)).filter((item): item is TripTrackingPoint => Boolean(item));
  const last = asTripTrackingPoint(payload?.last) ?? (items.length ? items[items.length - 1] : null);
  return {
    trip_id: payload?.trip_id ?? tripId,
    items,
    last,
  };
};

const formatCoords = (point: TripTrackingPoint | null, fallback: string) => {
  if (!point) return fallback;
  return `${point.lat.toFixed(6)}, ${point.lon.toFixed(6)}`;
};

const createSinceFromWindow = (windowKey: TrackingWindow) => new Date(Date.now() - windowToMs[windowKey]).toISOString();

const deviationTypeLabels: Record<TripDeviationType, string> = {
  LATE_START: "lateStart",
  ROUTE_DEVIATION: "routeDeviation",
  UNEXPECTED_STOP: "unexpectedStop",
};

const deviationTypeValues: Array<"ALL" | TripDeviationType> = ["ALL", "LATE_START", "ROUTE_DEVIATION", "UNEXPECTED_STOP"];

const severityClass = (severity?: TripDeviationSeverity | null) => {
  if (severity === "CRITICAL") return "neft-chip neft-chip-danger";
  if (severity === "WARN") return "neft-chip neft-chip-warn";
  return "neft-chip neft-chip-muted";
};

const impactClass = (impact?: TripSlaImpact["impact_level"] | null) => {
  if (impact === "HIGH") return "neft-chip neft-chip-danger";
  if (impact === "MEDIUM") return "neft-chip neft-chip-warn";
  if (impact === "LOW") return "neft-chip neft-chip-ok";
  return "neft-chip neft-chip-muted";
};

const asDeviationType = (value: unknown): TripDeviationType | null => {
  if (value === "LATE_START" || value === "ROUTE_DEVIATION" || value === "UNEXPECTED_STOP") return value;
  return null;
};

const asDeviationSeverity = (value: unknown): TripDeviationSeverity => {
  if (value === "WARN" || value === "CRITICAL" || value === "INFO") return value;
  return "INFO";
};

const normalizeTripDeviationsResponse = (tripId: string, value: unknown): TripDeviationsResponse => {
  const payload = value as Partial<TripDeviationsResponse> | null;
  const itemsRaw = Array.isArray(payload?.items) ? payload.items : [];
  const items = itemsRaw
    .map((entry) => {
      if (!entry || typeof entry !== "object") return null;
      const raw = entry as Record<string, unknown>;
      const type = asDeviationType(raw.type);
      if (!type || typeof raw.id !== "string" || typeof raw.ts !== "string") return null;
      return {
        id: raw.id,
        ts: raw.ts,
        type,
        severity: asDeviationSeverity(raw.severity),
        title: typeof raw.title === "string" ? raw.title : type,
        details: typeof raw.details === "string" ? raw.details : null,
        evidence: (raw.evidence && typeof raw.evidence === "object" ? raw.evidence : null) as TripDeviationEvent["evidence"],
        sla_impact: (raw.sla_impact && typeof raw.sla_impact === "object" ? raw.sla_impact : null) as TripDeviationEvent["sla_impact"],
      } satisfies TripDeviationEvent;
    })
    .filter((item): item is TripDeviationEvent => Boolean(item));

  return {
    trip_id: typeof payload?.trip_id === "string" ? payload.trip_id : tripId,
    items,
  };
};

export function TripDetailsPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const { tripId } = useParams<{ tripId: string }>();
  const [moduleUnavailable, setModuleUnavailable] = useState(false);
  const [moduleUnavailableReason, setModuleUnavailableReason] = useState<string | null>(null);
  const [isForbidden, setIsForbidden] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [trip, setTrip] = useState<TripDetail | null>(null);
  const [route, setRoute] = useState<RouteDetail | null>(null);
  const [activeTab, setActiveTab] = useState<"route" | "tracking" | "deviations" | "fuel" | "meta">("route");

  const [trackingWindow, setTrackingWindow] = useState<TrackingWindow>("30m");
  const [tracking, setTracking] = useState<TripTrackingResponse | null>(null);
  const [trackingError, setTrackingError] = useState<string | null>(null);
  const [trackingLoading, setTrackingLoading] = useState(false);
  const [eta, setEta] = useState<TripEta | null>(null);
  const [etaError, setEtaError] = useState<string | null>(null);
  const [lastPosition, setLastPosition] = useState<TripTrackingPoint | null>(null);
  const [copied, setCopied] = useState(false);
  const [deviationTypeFilter, setDeviationTypeFilter] = useState<"ALL" | TripDeviationType>("ALL");
  const [deviations, setDeviations] = useState<TripDeviationEvent[]>([]);
  const [deviationsLoading, setDeviationsLoading] = useState(false);
  const [deviationsError, setDeviationsError] = useState<string | null>(null);
  const [slaImpact, setSlaImpact] = useState<TripSlaImpact | null>(null);
  const [selectedDeviation, setSelectedDeviation] = useState<TripDeviationEvent | null>(null);
  const [fuel, setFuel] = useState<TripFuelResponse | null>(null);
  const lastTsRef = useRef<string | null>(null);
  const lastDeviationRef = useRef<string | null>(null);

  const loadTrip = useCallback(async () => {
    if (!user?.token || !tripId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    setIsForbidden(false);
    setModuleUnavailable(false);
    setModuleUnavailableReason(null);
    try {
      const response = await fetchTripById(user.token, tripId);
      setTrip(response);
      if (response.route) {
        setRoute(response.route);
      } else {
        try {
          const routeResponse = await fetchTripRoute(user.token, tripId);
          setRoute(routeResponse);
        } catch {
          setRoute(null);
        }
      }
    } catch (errorValue) {
      if (errorValue instanceof ApiError) {
        if (errorValue.status === 403) {
          setIsForbidden(true);
          setLoading(false);
          return;
        }
        if (isModuleDisabledError(errorValue)) {
          setModuleUnavailable(true);
          setModuleUnavailableReason(errorValue.message);
          setLoading(false);
          return;
        }
      }
      setError(errorValue instanceof Error ? errorValue.message : t("logisticsTrips.errors.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [t, tripId, user?.token]);

  useEffect(() => {
    void loadTrip();
  }, [loadTrip]);

  const loadTracking = useCallback(
    async (force = false) => {
      if (!user?.token || !tripId) return;
      if (!force) setTrackingLoading(true);
      setTrackingError(null);
      try {
        const since = createSinceFromWindow(trackingWindow);
        const trackingResponse = normalizeTrackingResponse(
          tripId,
          await fetchTripTracking(user.token, tripId, { since, limit: TRACKING_LIMIT }),
        );
        const ts = trackingResponse.last?.ts ?? null;
        if (!force && ts && ts === lastTsRef.current) {
          setTrackingLoading(false);
          return;
        }
        lastTsRef.current = ts;
        setTracking(trackingResponse);
        if (trackingResponse.last) {
          setLastPosition(trackingResponse.last);
        } else {
          try {
            const position = await fetchTripPosition(user.token, tripId);
            const normalized = asTripTrackingPoint(position);
            setLastPosition(normalized);
          } catch {
            setLastPosition(null);
          }
        }
      } catch (errorValue) {
        setTrackingError(errorValue instanceof Error ? errorValue.message : t("logisticsTrips.tracking.errors.loadFailed"));
      } finally {
        setTrackingLoading(false);
      }
    },
    [t, trackingWindow, tripId, user?.token],
  );

  const loadEta = useCallback(async () => {
    if (!user?.token || !tripId) return;
    setEtaError(null);
    try {
      const etaResponse = await fetchTripEta(user.token, tripId);
      setEta(etaResponse);
    } catch (errorValue) {
      setEtaError(errorValue instanceof Error ? errorValue.message : t("logisticsTrips.tracking.errors.etaFailed"));
    }
  }, [t, tripId, user?.token]);

  const loadDeviations = useCallback(
    async (force = false) => {
      if (!user?.token || !tripId) return;
      if (!force) setDeviationsLoading(true);
      setDeviationsError(null);
      try {
        const response = normalizeTripDeviationsResponse(
          tripId,
          await fetchTripDeviations(user.token, tripId, { limit: DEVIATIONS_LIMIT, type: deviationTypeFilter }),
        );
        const lastItem = response.items[0];
        const dedupKey = lastItem ? `${lastItem.id}:${lastItem.ts}` : "empty";
        if (!force && dedupKey === lastDeviationRef.current) {
          setDeviationsLoading(false);
          return;
        }
        lastDeviationRef.current = dedupKey;
        setDeviations(response.items);
        if (!slaImpact && response.items[0]?.sla_impact) {
          setSlaImpact(response.items[0].sla_impact);
        }
      } catch (errorValue) {
        setDeviationsError(errorValue instanceof Error ? errorValue.message : t("logisticsTrips.deviations.errors.loadFailed"));
      } finally {
        setDeviationsLoading(false);
      }
    },
    [deviationTypeFilter, slaImpact, t, tripId, user?.token],
  );


  const loadFuel = useCallback(async () => {
    if (!user?.token || !tripId) return;
    try {
      const response = await fetchTripFuel(user.token, tripId);
      setFuel(response);
    } catch {
      setFuel({ trip_id: tripId, items: [], totals: { liters: 0, amount: 0 }, alerts: [] });
    }
  }, [tripId, user?.token]);

  const loadSlaImpact = useCallback(async () => {
    if (!user?.token || !tripId) return;
    try {
      const response = await fetchTripSlaImpact(user.token, tripId);
      setSlaImpact(response);
    } catch {
      // optional endpoint may not be available; fallback to event payload
    }
  }, [tripId, user?.token]);

  const inProgress = trip?.status === "IN_PROGRESS";
  const trackingTabActive = activeTab === "tracking";
  const deviationsTabActive = activeTab === "deviations";
  const fuelTabActive = activeTab === "fuel";

  useEffect(() => {
    if (!trackingTabActive) return;
    void loadTracking(true);
    void loadEta();
  }, [loadEta, loadTracking, trackingTabActive]);


  useEffect(() => {
    if (!deviationsTabActive) return;
    void loadDeviations(true);
    void loadSlaImpact();
  }, [deviationsTabActive, loadDeviations, loadSlaImpact]);

  useEffect(() => {
    if (!fuelTabActive) return;
    void loadFuel();
  }, [fuelTabActive, loadFuel]);

  useEffect(() => {
    if (!fuelTabActive || !inProgress) return;
    const timer = window.setInterval(() => {
      void loadFuel();
    }, FUEL_POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [fuelTabActive, inProgress, loadFuel]);

  useEffect(() => {
    if (!deviationsTabActive || !inProgress) return;
    const timer = window.setInterval(() => {
      void loadDeviations();
      void loadSlaImpact();
    }, DEVIATIONS_POLL_INTERVAL_MS);

    return () => {
      window.clearInterval(timer);
    };
  }, [deviationsTabActive, inProgress, loadDeviations, loadSlaImpact]);

  useEffect(() => {
    if (!trackingTabActive || !inProgress) return;
    const trackingTimer = window.setInterval(() => {
      void loadTracking();
    }, 10000);
    const etaTimer = window.setInterval(() => {
      void loadEta();
    }, 30000);

    return () => {
      window.clearInterval(trackingTimer);
      window.clearInterval(etaTimer);
    };
  }, [inProgress, loadEta, loadTracking, trackingTabActive]);

  const handleCopyCoords = useCallback(async () => {
    if (!lastPosition) return;
    const text = `${lastPosition.lat},${lastPosition.lon}`;
    await navigator.clipboard.writeText(text);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }, [lastPosition]);

  const stopColumns: Column<TripStop>[] = useMemo(
    () => [
      {
        key: "seq",
        title: t("logisticsTrips.stops.columns.seq"),
        render: (row) => row.seq,
      },
      {
        key: "type",
        title: t("logisticsTrips.stops.columns.type"),
        render: (row) => {
          if (row.type === "START") return t("logisticsTrips.stops.types.start");
          if (row.type === "END") return t("logisticsTrips.stops.types.end");
          return t("logisticsTrips.stops.types.stop");
        },
      },
      {
        key: "label",
        title: t("logisticsTrips.stops.columns.label"),
        render: (row) => row.label ?? t("common.notAvailable"),
      },
      {
        key: "planned",
        title: t("logisticsTrips.stops.columns.planned"),
        render: (row) => formatDateValue(row.planned_at, t("common.notAvailable")),
      },
      {
        key: "actual",
        title: t("logisticsTrips.stops.columns.actual"),
        render: (row) => formatDateValue(row.actual_at, t("common.notAvailable")),
      },
    ],
    [t],
  );

  const breadcrumbColumns: Column<TripTrackingPoint>[] = useMemo(
    () => [
      {
        key: "ts",
        title: t("logisticsTrips.tracking.breadcrumbs.columns.time"),
        render: (row) => formatDateValue(row.ts, t("common.notAvailable")),
      },
      {
        key: "coords",
        title: t("logisticsTrips.tracking.breadcrumbs.columns.coords"),
        render: (row) => `${row.lat.toFixed(6)}, ${row.lon.toFixed(6)}`,
      },
      {
        key: "speed",
        title: t("logisticsTrips.tracking.breadcrumbs.columns.speed"),
        render: (row) => (typeof row.speed_kmh === "number" ? row.speed_kmh.toFixed(1) : t("common.notAvailable")),
      },
    ],
    [t],
  );

  const deviationColumns: Column<TripDeviationEvent>[] = useMemo(
    () => [
      { key: "ts", title: t("logisticsTrips.deviations.columns.time"), render: (row) => formatDateValue(row.ts, t("common.notAvailable")) },
      {
        key: "type",
        title: t("logisticsTrips.deviations.columns.type"),
        render: (row) => <span className="neft-chip neft-chip-muted">{t(`logisticsTrips.deviations.types.${deviationTypeLabels[row.type]}`)}</span>,
      },
      {
        key: "severity",
        title: t("logisticsTrips.deviations.columns.severity"),
        render: (row) => <span className={severityClass(row.severity)}>{row.severity}</span>,
      },
      { key: "title", title: t("logisticsTrips.deviations.columns.title"), render: (row) => row.title },
      {
        key: "summary",
        title: t("logisticsTrips.deviations.columns.summary"),
        render: (row) => {
          if (typeof row.evidence?.delta_minutes === "number") return t("logisticsTrips.deviations.evidence.delta", { value: row.evidence.delta_minutes });
          if (typeof row.evidence?.distance_off_route_km === "number") return t("logisticsTrips.deviations.evidence.offRoute", { value: row.evidence.distance_off_route_km });
          if (typeof row.evidence?.stop_minutes === "number") return t("logisticsTrips.deviations.evidence.stop", { value: row.evidence.stop_minutes });
          return row.details ?? t("common.notAvailable");
        },
      },
      {
        key: "open",
        title: t("logisticsTrips.deviations.columns.actions"),
        render: (row) => (
          <button type="button" className="ghost" onClick={(event) => { event.stopPropagation(); setSelectedDeviation(row); }}>
            {t("logisticsTrips.deviations.open")}
          </button>
        ),
      },
    ],
    [t],
  );

  if (moduleUnavailable) {
    return <ModuleUnavailablePage title={t("logisticsTrips.title")} description={moduleUnavailableReason ?? t("logisticsTrips.errors.moduleDisabled")} />;
  }

  if (isForbidden) {
    return <AppForbiddenState message={t("logisticsTrips.errors.noPermission")} />;
  }

  if (loading) {
    return <AppLoadingState label={t("logisticsTrips.loading")} />;
  }

  if (error) {
    return <AppErrorState message={error} onRetry={() => void loadTrip()} />;
  }

  if (!trip) {
    return <AppEmptyState title={t("logisticsTrips.emptyTitle")} description={t("logisticsTrips.emptyDescription")} />;
  }

  const origin = trip.origin?.label ?? t("common.notAvailable");
  const destination = trip.destination?.label ?? t("common.notAvailable");
  const plannedRange = `${formatDateValue(trip.start_planned_at, t("common.notAvailable"))} — ${formatDateValue(
    trip.end_planned_at,
    t("common.notAvailable"),
  )}`;
  const actualRange =
    trip.status === "CREATED"
      ? t("common.notAvailable")
      : `${formatDateValue(trip.start_actual_at, t("common.notAvailable"))} — ${formatDateValue(
          trip.end_actual_at,
          t("common.notAvailable"),
        )}`;
  const stops = route?.stops ?? [];
  const breadcrumbs = tracking?.items ?? [];

  return (
    <div className="page">
      <div className="page-header">
        <div className="stack">
          <h1>{t("logisticsTrips.detailTitle")}</h1>
          <StatusBadge status={trip.status} />
        </div>
      </div>
      <div className="card stack">
        <div className="grid two">
          <div>
            <div className="muted small">{t("logisticsTrips.columns.vehicle")}</div>
            <div>{trip.vehicle?.plate ?? t("common.notAvailable")}</div>
          </div>
          <div>
            <div className="muted small">{t("logisticsTrips.columns.driver")}</div>
            <div>{trip.driver?.name ?? t("common.notAvailable")}</div>
          </div>
          <div>
            <div className="muted small">{t("logisticsTrips.routeSummary")}</div>
            <div>
              {origin} → {destination}
            </div>
          </div>
          <div>
            <div className="muted small">{t("logisticsTrips.plannedLabel")}</div>
            <div>{plannedRange}</div>
          </div>
          <div>
            <div className="muted small">{t("logisticsTrips.actualLabel")}</div>
            <div>{actualRange}</div>
          </div>
        </div>
      </div>

      <div className="card stack">
        <h2>{t("logisticsTrips.timelineTitle")}</h2>
        <ul className="timeline">
          {statusSteps.map((step) => {
            const isCurrent = step === trip.status;
            return (
              <li key={step}>
                <span className="timeline__marker" />
                <div>
                  <div className={isCurrent ? "" : "muted"}>
                    {step === "CREATED"
                      ? t("logisticsTrips.statusCreated")
                      : step === "IN_PROGRESS"
                        ? t("logisticsTrips.statusInProgress")
                        : t("logisticsTrips.statusCompleted")}
                  </div>
                  {isCurrent ? <div className="small muted">{t("logisticsTrips.currentStatus")}</div> : null}
                </div>
              </li>
            );
          })}
        </ul>
      </div>

      <div className="tabs">
        <button type="button" className={activeTab === "route" ? "secondary" : "ghost"} onClick={() => setActiveTab("route")}>
          {t("logisticsTrips.tabs.route")}
        </button>
        <button type="button" className={activeTab === "tracking" ? "secondary" : "ghost"} onClick={() => setActiveTab("tracking")}>
          {t("logisticsTrips.tabs.tracking")}
        </button>
        <button type="button" className={activeTab === "deviations" ? "secondary" : "ghost"} onClick={() => setActiveTab("deviations")}>
          {t("logisticsTrips.tabs.deviations")}
        </button>
        <button type="button" className={activeTab === "fuel" ? "secondary" : "ghost"} onClick={() => setActiveTab("fuel")}>
          Fuel
        </button>
        <button type="button" className={activeTab === "meta" ? "secondary" : "ghost"} onClick={() => setActiveTab("meta")}>
          {t("logisticsTrips.tabs.meta")}
        </button>
      </div>

      {activeTab === "route" ? (
        <div className="card stack">
          <h2>{t("logisticsTrips.routeTitle")}</h2>
          {route?.distance_km !== undefined && route?.distance_km !== null ? (
            <div className="muted small">{t("logisticsTrips.distanceLabel", { value: route.distance_km })}</div>
          ) : null}
          {route?.eta_minutes !== undefined && route?.eta_minutes !== null ? (
            <div className="muted small">{t("logisticsTrips.etaLabel", { value: route.eta_minutes })}</div>
          ) : null}
          {stops.length ? (
            <Table columns={stopColumns} data={stops} />
          ) : (
            <AppEmptyState title={t("logisticsTrips.stops.emptyTitle")} description={t("logisticsTrips.stops.emptyDescription")} />
          )}
        </div>
      ) : null}

      {activeTab === "tracking" ? (
        <>
          <div className="card stack">
            <h2>{t("logisticsTrips.tracking.lastKnownPosition")}</h2>
            {trackingError ? <div className="error-banner">{trackingError}</div> : null}
            <div className="grid two">
              <div>
                <div className="muted small">{t("logisticsTrips.tracking.positionTime")}</div>
                <div>{formatDateValue(lastPosition?.ts, t("common.notAvailable"))}</div>
              </div>
              <div>
                <div className="muted small">{t("logisticsTrips.tracking.positionCoords")}</div>
                <div>{formatCoords(lastPosition, t("common.notAvailable"))}</div>
              </div>
              <div>
                <div className="muted small">{t("logisticsTrips.tracking.positionSpeed")}</div>
                <div>{typeof lastPosition?.speed_kmh === "number" ? `${lastPosition.speed_kmh.toFixed(1)} km/h` : t("common.notAvailable")}</div>
              </div>
              <div>
                <div className="muted small">{t("logisticsTrips.tracking.positionAccuracy")}</div>
                <div>{typeof lastPosition?.accuracy_m === "number" ? `${lastPosition.accuracy_m.toFixed(0)} m` : t("common.notAvailable")}</div>
              </div>
            </div>
            <div>
              <button type="button" className="ghost" onClick={() => void handleCopyCoords()} disabled={!lastPosition}>
                {copied ? t("logisticsTrips.tracking.copied") : t("logisticsTrips.tracking.copyCoords")}
              </button>
            </div>
          </div>

          <div className="card stack">
            <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
              <h2>{t("logisticsTrips.tracking.breadcrumbs.title")}</h2>
              <select
                aria-label={t("logisticsTrips.tracking.breadcrumbs.windowLabel")}
                value={trackingWindow}
                onChange={(event) => setTrackingWindow(event.target.value as TrackingWindow)}
              >
                <option value="30m">{t("logisticsTrips.tracking.breadcrumbs.window30m")}</option>
                <option value="2h">{t("logisticsTrips.tracking.breadcrumbs.window2h")}</option>
                <option value="24h">{t("logisticsTrips.tracking.breadcrumbs.window24h")}</option>
              </select>
            </div>
            <Table
              columns={breadcrumbColumns}
              data={breadcrumbs}
              loading={trackingLoading}
              errorState={
                trackingError
                  ? {
                      title: t("logisticsTrips.tracking.errors.loadFailed"),
                      description: trackingError,
                      actionLabel: t("errors.retry"),
                      actionOnClick: () => void loadTracking(true),
                    }
                  : undefined
              }
              emptyState={{
                title: t("logisticsTrips.tracking.breadcrumbs.emptyTitle"),
                description: t("logisticsTrips.tracking.breadcrumbs.emptyDescription"),
              }}
            />
          </div>

          <div className="card stack">
            <h2>{t("logisticsTrips.tracking.eta.title")}</h2>
            {etaError ? (
              <AppErrorState message={etaError} compact onRetry={() => void loadEta()} />
            ) : (
              <div className="grid two">
                <div>
                  <div className="muted small">{t("logisticsTrips.tracking.eta.etaAt")}</div>
                  <div>{formatDateValue(eta?.eta_at, t("common.notAvailable"))}</div>
                </div>
                <div>
                  <div className="muted small">{t("logisticsTrips.tracking.eta.etaMinutes")}</div>
                  <div>{typeof eta?.eta_minutes === "number" ? eta.eta_minutes : t("common.notAvailable")}</div>
                </div>
                <div>
                  <div className="muted small">{t("logisticsTrips.tracking.eta.updatedAt")}</div>
                  <div>{formatDateValue(eta?.updated_at, t("common.notAvailable"))}</div>
                </div>
                <div>
                  <div className="muted small">{t("logisticsTrips.tracking.eta.method")}</div>
                  <div>{eta?.method ?? t("common.notAvailable")}</div>
                </div>
                <div>
                  <div className="muted small">{t("logisticsTrips.tracking.eta.confidence")}</div>
                  <div>{typeof eta?.confidence === "number" ? eta.confidence.toFixed(2) : t("common.notAvailable")}</div>
                </div>
              </div>
            )}
          </div>
        </>
      ) : null}

      {activeTab === "deviations" ? (
        <>
          <div className="card stack">
            <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
              <h2>{t("logisticsTrips.deviations.sla.title")}</h2>
              <span className={impactClass(slaImpact?.impact_level ?? "NONE")}>{slaImpact?.impact_level ?? "NONE"}</span>
            </div>
            <div className="grid two">
              <div>
                <div className="muted small">{t("logisticsTrips.deviations.sla.firstResponseDueAt")}</div>
                <div>{formatDateValue(slaImpact?.first_response_due_at, t("common.notAvailable"))}</div>
              </div>
              <div>
                <div className="muted small">{t("logisticsTrips.deviations.sla.resolveDueAt")}</div>
                <div>{formatDateValue(slaImpact?.resolve_due_at, t("common.notAvailable"))}</div>
              </div>
              <div>
                <div className="muted small">{t("logisticsTrips.deviations.sla.counts")}</div>
                <div>
                  {deviations.filter((item) => item.type === "LATE_START").length} / {deviations.filter((item) => item.type === "ROUTE_DEVIATION").length} / {deviations.filter((item) => item.type === "UNEXPECTED_STOP").length}
                </div>
              </div>
            </div>
          </div>

          <div className="card stack">
            <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
              <h2>{t("logisticsTrips.deviations.title")}</h2>
              <select aria-label={t("logisticsTrips.deviations.filters.type")} value={deviationTypeFilter} onChange={(event) => setDeviationTypeFilter(event.target.value as "ALL" | TripDeviationType)}>
                {deviationTypeValues.map((value) => (
                  <option key={value} value={value}>
                    {value === "ALL" ? t("logisticsTrips.deviations.filters.all") : t(`logisticsTrips.deviations.types.${deviationTypeLabels[value]}`)}
                  </option>
                ))}
              </select>
            </div>
            <Table
              columns={deviationColumns}
              data={deviations}
              loading={deviationsLoading}
              errorState={
                deviationsError
                  ? {
                      title: t("logisticsTrips.deviations.errors.loadFailed"),
                      description: deviationsError,
                      actionLabel: t("errors.retry"),
                      actionOnClick: () => void loadDeviations(true),
                    }
                  : undefined
              }
              emptyState={{ title: t("logisticsTrips.deviations.emptyTitle"), description: t("logisticsTrips.deviations.emptyDescription") }}
            />
          </div>

          {selectedDeviation ? (
            <div className="modal-backdrop" role="dialog" aria-modal="true">
              <div className="modal-card stack">
                <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                  <h3>{selectedDeviation.title}</h3>
                  <button type="button" className="ghost" onClick={() => setSelectedDeviation(null)}>
                    {t("common.close")}
                  </button>
                </div>
                <div>{selectedDeviation.details ?? t("common.notAvailable")}</div>
                <pre className="mono">{formatMeta(selectedDeviation.evidence as Record<string, unknown> | null)}</pre>
              </div>
            </div>
          ) : null}
        </>
      ) : null}

      {activeTab === "fuel" ? (
        <div className="stack gap-12">
          <div className="grid grid-3">
            <article className="card"><h3>Total liters</h3><div>{fuel?.totals?.liters ?? 0}</div></article>
            <article className="card"><h3>Total amount</h3><div>{fuel?.totals?.amount ?? 0}</div></article>
            <article className="card"><h3>Alerts</h3><div>{fuel?.alerts?.length ?? 0}</div></article>
          </div>
          <Table
            columns={[
              { key: "ts", title: "Time", render: (row) => formatDateValue(row.ts, "-") },
              { key: "station", title: "Station", render: (row) => row.station ?? "-" },
              { key: "liters", title: "Liters", render: (row) => String(row.liters ?? 0) },
              { key: "amount", title: "Amount", render: (row) => String(row.amount ?? 0) },
              { key: "score", title: "Score", render: (row) => String(row.score ?? 0) },
            ]}
            data={fuel?.items ?? []}
            getRowId={(row) => row.fuel_tx_id}
            emptyState={{ title: "No fuel transactions", description: "No linked fuel operations for this trip" }}
          />
        </div>
      ) : null}

      {activeTab === "meta" ? (
        <div className="card stack">
          <details open>
            <summary>{t("logisticsTrips.metaTitle")}</summary>
            <pre className="mono">{formatMeta(trip.meta)}</pre>
          </details>
        </div>
      ) : null}
    </div>
  );
}
