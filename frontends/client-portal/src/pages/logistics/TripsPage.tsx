import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { useI18n } from "../../i18n";
import { fetchTrips } from "../../api/logistics";
import type { PaginatedResponse, TripListItem } from "../../types/logistics";
import type { Column } from "../../components/common/Table";
import { Table } from "../../components/common/Table";
import { StatusBadge } from "../../components/StatusBadge";
import { AppForbiddenState } from "../../components/states";
import { ModuleUnavailablePage } from "../ModuleUnavailablePage";
import { ApiError } from "../../api/http";
import { formatDateTime } from "../../utils/format";

const PAGE_LIMIT = 10;

type PaginationState = {
  limit: number;
  offset: number;
};

type PageState<T> = {
  items: T[];
  total: number;
};

const isModuleDisabledError = (error: ApiError) => {
  const code = error.errorCode ?? "";
  return code.includes("module_disabled") || error.message.includes("module_disabled");
};

const formatRange = (start: string | null | undefined, end: string | null | undefined, fallback: string) => {
  if (!start && !end) return fallback;
  const startValue = start ? formatDateTime(start) : fallback;
  const endValue = end ? formatDateTime(end) : fallback;
  return `${startValue} — ${endValue}`;
};

export function TripsPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [moduleUnavailable, setModuleUnavailable] = useState(false);
  const [moduleUnavailableReason, setModuleUnavailableReason] = useState<string | null>(null);
  const [isForbidden, setIsForbidden] = useState(false);

  const [pagination, setPagination] = useState<PaginationState>({ limit: PAGE_LIMIT, offset: 0 });
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [state, setState] = useState<PageState<TripListItem>>({ items: [], total: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const handleApiError = useCallback(
    (errorValue: unknown) => {
      if (errorValue instanceof ApiError) {
        if (errorValue.status === 403) {
          setIsForbidden(true);
          return;
        }
        if (isModuleDisabledError(errorValue)) {
          setModuleUnavailable(true);
          setModuleUnavailableReason(errorValue.message);
          return;
        }
      }
      setError(errorValue instanceof Error ? errorValue.message : t("logisticsTrips.errors.loadFailed"));
    },
    [t],
  );

  const loadTrips = useCallback(async () => {
    if (!user?.token) return;
    setLoading(true);
    setError(null);
    setIsForbidden(false);
    setModuleUnavailable(false);
    setModuleUnavailableReason(null);
    try {
      const response: PaginatedResponse<TripListItem> = await fetchTrips(user.token, {
        status: status || undefined,
        q: search.trim() || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        limit: pagination.limit,
        offset: pagination.offset,
      });
      setState({ items: response.items ?? [], total: response.total ?? 0 });
    } catch (errorValue) {
      handleApiError(errorValue);
    } finally {
      setLoading(false);
    }
  }, [dateFrom, dateTo, handleApiError, pagination.limit, pagination.offset, search, status, user?.token]);

  useEffect(() => {
    void loadTrips();
  }, [loadTrips]);

  const columns: Column<TripListItem>[] = useMemo(
    () => [
      {
        key: "status",
        title: t("logisticsTrips.columns.status"),
        render: (row) => <StatusBadge status={row.status} />,
      },
      {
        key: "vehicle",
        title: t("logisticsTrips.columns.vehicle"),
        render: (row) => row.vehicle?.plate ?? t("common.notAvailable"),
      },
      {
        key: "driver",
        title: t("logisticsTrips.columns.driver"),
        render: (row) => row.driver?.name ?? t("common.notAvailable"),
      },
      {
        key: "route",
        title: t("logisticsTrips.columns.route"),
        render: (row) => {
          const origin = row.origin?.label ?? t("common.notAvailable");
          const destination = row.destination?.label ?? t("common.notAvailable");
          return `${origin} → ${destination}`;
        },
      },
      {
        key: "planned",
        title: t("logisticsTrips.columns.planned"),
        render: (row) => formatRange(row.start_planned_at, row.end_planned_at, t("common.notAvailable")),
      },
      {
        key: "actual",
        title: t("logisticsTrips.columns.actual"),
        render: (row) =>
          row.status === "CREATED"
            ? t("common.notAvailable")
            : formatRange(row.start_actual_at, row.end_actual_at, t("common.notAvailable")),
      },
      {
        key: "actions",
        title: t("logisticsTrips.columns.actions"),
        render: (row) => (
          <Link className="ghost" to={`/logistics/trips/${row.id}`}>
            {t("common.open")}
          </Link>
        ),
      },
    ],
    [t],
  );

  const page = Math.floor(pagination.offset / pagination.limit) + 1;
  const pages = Math.max(1, Math.ceil(state.total / pagination.limit));

  if (moduleUnavailable) {
    return <ModuleUnavailablePage title={t("logisticsTrips.title")} description={moduleUnavailableReason ?? t("logisticsTrips.errors.moduleDisabled")} />;
  }

  if (isForbidden) {
    return <AppForbiddenState message={t("logisticsTrips.errors.noPermission")} />;
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>{t("logisticsTrips.title")}</h1>
      </div>
      <div className="filters">
        <div className="filter">
          <span className="label">{t("logisticsTrips.filters.status")}</span>
          <select
            value={status}
            aria-label={t("logisticsTrips.filters.status")}
            onChange={(event) => {
              setStatus(event.target.value);
              setPagination((prev) => ({ ...prev, offset: 0 }));
            }}
          >
            <option value="">{t("logisticsTrips.statusAll")}</option>
            <option value="CREATED">{t("logisticsTrips.statusCreated")}</option>
            <option value="IN_PROGRESS">{t("logisticsTrips.statusInProgress")}</option>
            <option value="COMPLETED">{t("logisticsTrips.statusCompleted")}</option>
          </select>
        </div>
        <div className="filter filter--wide">
          <span className="label">{t("logisticsTrips.filters.period")}</span>
          <div className="grid two">
            <input
              type="date"
              value={dateFrom}
              aria-label={t("logisticsTrips.filters.period")}
              onChange={(event) => {
                setDateFrom(event.target.value);
                setPagination((prev) => ({ ...prev, offset: 0 }));
              }}
            />
            <input
              type="date"
              value={dateTo}
              aria-label={t("logisticsTrips.filters.period")}
              onChange={(event) => {
                setDateTo(event.target.value);
                setPagination((prev) => ({ ...prev, offset: 0 }));
              }}
            />
          </div>
        </div>
        <div className="filter filter--wide">
          <span className="label">{t("logisticsTrips.filters.search")}</span>
          <input
            value={search}
            aria-label={t("logisticsTrips.filters.search")}
            onChange={(event) => {
              setSearch(event.target.value);
              setPagination((prev) => ({ ...prev, offset: 0 }));
            }}
            placeholder={t("logisticsTrips.searchPlaceholder")}
          />
        </div>
      </div>
      <Table
        columns={columns}
        data={state.items}
        loading={loading}
        errorState={
          error
            ? {
                title: t("logisticsTrips.errors.loadFailed"),
                description: error,
                actionLabel: t("errors.retry"),
                actionOnClick: () => void loadTrips(),
              }
            : undefined
        }
        emptyState={{
          title: t("logisticsTrips.emptyTitle"),
          description: t("logisticsTrips.emptyDescription"),
        }}
      />
      <div className="pagination">
        <button
          type="button"
          className="secondary"
          onClick={() =>
            setPagination((prev) => ({ ...prev, offset: Math.max(0, prev.offset - prev.limit) }))
          }
          disabled={pagination.offset === 0 || loading}
        >
          {t("common.back")}
        </button>
        <span className="muted">{t("logisticsTrips.pagination", { page, total: pages })}</span>
        <button
          type="button"
          className="secondary"
          onClick={() => setPagination((prev) => ({ ...prev, offset: prev.offset + prev.limit }))}
          disabled={pagination.offset + pagination.limit >= state.total || loading}
        >
          {t("common.next")}
        </button>
      </div>
    </div>
  );
}
