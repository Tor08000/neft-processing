import { type ChangeEvent, type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { useI18n } from "../../i18n";
import { createTrip, fetchTrips } from "../../api/logistics";
import type { PaginatedResponse, TripCreatePayload, TripListItem } from "../../types/logistics";
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

type CreateTripFormState = {
  title: string;
  originLabel: string;
  originLat: string;
  originLon: string;
  destinationLabel: string;
  destinationLat: string;
  destinationLon: string;
  startPlannedAt: string;
  endPlannedAt: string;
};

const EMPTY_CREATE_TRIP_FORM: CreateTripFormState = {
  title: "",
  originLabel: "",
  originLat: "",
  originLon: "",
  destinationLabel: "",
  destinationLat: "",
  destinationLon: "",
  startPlannedAt: "",
  endPlannedAt: "",
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

const optionalDateTime = (value: string): string | null => (value ? new Date(value).toISOString() : null);

const requiredCoordinate = (value: string): number | null => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
};

const buildCreatePayload = (form: CreateTripFormState): TripCreatePayload | null => {
  const originLat = requiredCoordinate(form.originLat);
  const originLon = requiredCoordinate(form.originLon);
  const destinationLat = requiredCoordinate(form.destinationLat);
  const destinationLon = requiredCoordinate(form.destinationLon);
  if (
    !form.originLabel.trim() ||
    !form.destinationLabel.trim() ||
    originLat === null ||
    originLon === null ||
    destinationLat === null ||
    destinationLon === null
  ) {
    return null;
  }
  return {
    title: form.title.trim() || null,
    start_planned_at: optionalDateTime(form.startPlannedAt),
    end_planned_at: optionalDateTime(form.endPlannedAt),
    origin: { label: form.originLabel.trim(), lat: originLat, lon: originLon },
    destination: { label: form.destinationLabel.trim(), lat: destinationLat, lon: destinationLon },
    stops: [],
  };
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
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<CreateTripFormState>(EMPTY_CREATE_TRIP_FORM);
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createSuccess, setCreateSuccess] = useState<string | null>(null);

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

  const updateCreateField = useCallback(
    (field: keyof CreateTripFormState) => (event: ChangeEvent<HTMLInputElement>) => {
      setCreateForm((prev) => ({ ...prev, [field]: event.target.value }));
      setCreateError(null);
    },
    [],
  );

  const handleCreateSubmit = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!user?.token) return;
      const payload = buildCreatePayload(createForm);
      if (!payload) {
        setCreateError(t("logisticsTrips.create.validationRequired"));
        return;
      }
      setCreateLoading(true);
      setCreateError(null);
      try {
        await createTrip(user.token, payload);
        setCreateForm(EMPTY_CREATE_TRIP_FORM);
        setIsCreateOpen(false);
        setCreateSuccess(t("logisticsTrips.create.created"));
        setPagination((prev) => ({ ...prev, offset: 0 }));
        await loadTrips();
      } catch (errorValue) {
        setCreateError(errorValue instanceof Error ? errorValue.message : t("logisticsTrips.create.error"));
      } finally {
        setCreateLoading(false);
      }
    },
    [createForm, loadTrips, t, user?.token],
  );

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
        <div className="actions">
          {createSuccess ? <span className="pill pill--accent" role="status">{createSuccess}</span> : null}
          <button
            type="button"
            className="primary"
            onClick={() => {
              setCreateError(null);
              setCreateSuccess(null);
              setIsCreateOpen(true);
            }}
          >
            {t("logisticsTrips.create.open")}
          </button>
        </div>
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
            <option value="CANCELLED">{t("logisticsTrips.statusCancelled")}</option>
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
      {isCreateOpen ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="create-trip-title">
          <form className="modal-card stack" onSubmit={handleCreateSubmit}>
            <div className="section-header">
              <h2 id="create-trip-title">{t("logisticsTrips.create.title")}</h2>
              <button
                type="button"
                className="secondary"
                onClick={() => {
                  setIsCreateOpen(false);
                  setCreateError(null);
                }}
                disabled={createLoading}
              >
                {t("actions.close")}
              </button>
            </div>
            <div className="form-grid">
              <label className="form-field form-grid__full">
                <span>{t("logisticsTrips.create.tripTitle")}</span>
                <input value={createForm.title} onChange={updateCreateField("title")} />
              </label>
              <label className="form-field">
                <span>{t("logisticsTrips.create.origin")}</span>
                <input value={createForm.originLabel} onChange={updateCreateField("originLabel")} required />
              </label>
              <label className="form-field">
                <span>{t("logisticsTrips.create.destination")}</span>
                <input value={createForm.destinationLabel} onChange={updateCreateField("destinationLabel")} required />
              </label>
              <label className="form-field">
                <span>{t("logisticsTrips.create.originLat")}</span>
                <input type="number" step="0.000001" value={createForm.originLat} onChange={updateCreateField("originLat")} required />
              </label>
              <label className="form-field">
                <span>{t("logisticsTrips.create.originLon")}</span>
                <input type="number" step="0.000001" value={createForm.originLon} onChange={updateCreateField("originLon")} required />
              </label>
              <label className="form-field">
                <span>{t("logisticsTrips.create.destinationLat")}</span>
                <input type="number" step="0.000001" value={createForm.destinationLat} onChange={updateCreateField("destinationLat")} required />
              </label>
              <label className="form-field">
                <span>{t("logisticsTrips.create.destinationLon")}</span>
                <input type="number" step="0.000001" value={createForm.destinationLon} onChange={updateCreateField("destinationLon")} required />
              </label>
              <label className="form-field">
                <span>{t("logisticsTrips.create.plannedStart")}</span>
                <input type="datetime-local" value={createForm.startPlannedAt} onChange={updateCreateField("startPlannedAt")} />
              </label>
              <label className="form-field">
                <span>{t("logisticsTrips.create.plannedEnd")}</span>
                <input type="datetime-local" value={createForm.endPlannedAt} onChange={updateCreateField("endPlannedAt")} />
              </label>
            </div>
            {createError ? <div className="error-state">{createError}</div> : null}
            <div className="actions">
              <button type="submit" className="primary" disabled={createLoading}>
                {createLoading ? t("common.loading") : t("logisticsTrips.create.submit")}
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => {
                  setIsCreateOpen(false);
                  setCreateError(null);
                }}
                disabled={createLoading}
              >
                {t("actions.cancel")}
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </div>
  );
}
