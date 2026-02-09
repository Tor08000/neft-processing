import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { useI18n } from "../../i18n";
import { fetchTripById, fetchTripRoute } from "../../api/logistics";
import type { RouteDetail, TripDetail, TripStatus, TripStop } from "../../types/logistics";
import { StatusBadge } from "../../components/StatusBadge";
import type { Column } from "../../components/common/Table";
import { Table } from "../../components/common/Table";
import { AppErrorState, AppForbiddenState, AppLoadingState, AppEmptyState } from "../../components/states";
import { ModuleUnavailablePage } from "../ModuleUnavailablePage";
import { ApiError } from "../../api/http";
import { formatDateTime } from "../../utils/format";

const statusSteps: TripStatus[] = ["CREATED", "IN_PROGRESS", "COMPLETED"];

const isModuleDisabledError = (error: ApiError) => {
  const code = error.errorCode ?? "";
  return code.includes("module_disabled") || error.message.includes("module_disabled");
};

const formatMeta = (meta?: Record<string, unknown> | null) => JSON.stringify(meta ?? {}, null, 2);

const formatDateValue = (value: string | null | undefined, fallback: string) =>
  value ? formatDateTime(value) : fallback;

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
        } catch (routeError) {
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

      <div className="card stack">
        <details>
          <summary>{t("logisticsTrips.metaTitle")}</summary>
          <pre className="mono">{formatMeta(trip.meta)}</pre>
        </details>
      </div>
    </div>
  );
}
