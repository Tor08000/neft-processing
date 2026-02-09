import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { useI18n } from "../../i18n";
import { fetchDrivers, fetchVehicles } from "../../api/logistics";
import type { DriverDTO, PaginatedResponse, VehicleDTO } from "../../types/logistics";
import type { Column } from "../../components/common/Table";
import { Table } from "../../components/common/Table";
import { StatusBadge } from "../../components/StatusBadge";
import { AppForbiddenState } from "../../components/states";
import { ModuleUnavailablePage } from "../ModuleUnavailablePage";
import { ApiError } from "../../api/http";

const PAGE_LIMIT = 10;

type TabKey = "vehicles" | "drivers";

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

const formatMeta = (meta?: Record<string, unknown> | null) => JSON.stringify(meta ?? {}, null, 2);

const DetailModal = ({
  title,
  fields,
  meta,
  onClose,
  closeLabel,
  metaLabel,
}: {
  title: string;
  fields: Array<{ label: string; value: string }>;
  meta?: Record<string, unknown> | null;
  onClose: () => void;
  closeLabel: string;
  metaLabel: string;
}) => (
  <div className="modal-backdrop" role="dialog" aria-modal="true">
    <div className="modal-card stack">
      <h2>{title}</h2>
      <div className="grid two">
        {fields.map((field) => (
          <div key={field.label}>
            <div className="muted small">{field.label}</div>
            <div>{field.value}</div>
          </div>
        ))}
      </div>
      <details>
        <summary>{metaLabel}</summary>
        <pre className="mono">{formatMeta(meta)}</pre>
      </details>
      <div className="actions">
        <button type="button" className="secondary" onClick={onClose}>
          {closeLabel}
        </button>
      </div>
    </div>
  </div>
);

export function FleetPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [activeTab, setActiveTab] = useState<TabKey>("vehicles");
  const [moduleUnavailable, setModuleUnavailable] = useState(false);
  const [moduleUnavailableReason, setModuleUnavailableReason] = useState<string | null>(null);
  const [isForbidden, setIsForbidden] = useState(false);

  const [vehiclePagination, setVehiclePagination] = useState<PaginationState>({ limit: PAGE_LIMIT, offset: 0 });
  const [vehicleSearch, setVehicleSearch] = useState("");
  const [vehicleStatus, setVehicleStatus] = useState("");
  const [vehicleState, setVehicleState] = useState<PageState<VehicleDTO>>({ items: [], total: 0 });
  const [vehicleLoading, setVehicleLoading] = useState(true);
  const [vehicleError, setVehicleError] = useState<string | null>(null);

  const [driverPagination, setDriverPagination] = useState<PaginationState>({ limit: PAGE_LIMIT, offset: 0 });
  const [driverSearch, setDriverSearch] = useState("");
  const [driverStatus, setDriverStatus] = useState("");
  const [driverState, setDriverState] = useState<PageState<DriverDTO>>({ items: [], total: 0 });
  const [driverLoading, setDriverLoading] = useState(true);
  const [driverError, setDriverError] = useState<string | null>(null);

  const [selectedVehicle, setSelectedVehicle] = useState<VehicleDTO | null>(null);
  const [selectedDriver, setSelectedDriver] = useState<DriverDTO | null>(null);

  const handleApiError = useCallback(
    (error: unknown, setError: (message: string) => void) => {
      if (error instanceof ApiError) {
        if (error.status === 403) {
          setIsForbidden(true);
          return;
        }
        if (isModuleDisabledError(error)) {
          setModuleUnavailable(true);
          setModuleUnavailableReason(error.message);
          return;
        }
      }
      setError(error instanceof Error ? error.message : t("logisticsFleet.errors.loadFailed"));
    },
    [t],
  );

  const loadVehicles = useCallback(async () => {
    if (!user?.token) return;
    setVehicleLoading(true);
    setVehicleError(null);
    setIsForbidden(false);
    setModuleUnavailable(false);
    setModuleUnavailableReason(null);
    try {
      const response: PaginatedResponse<VehicleDTO> = await fetchVehicles(user.token, {
        status: vehicleStatus || undefined,
        q: vehicleSearch.trim() || undefined,
        limit: vehiclePagination.limit,
        offset: vehiclePagination.offset,
      });
      setVehicleState({
        items: response.items ?? [],
        total: response.total ?? 0,
      });
    } catch (error) {
      handleApiError(error, setVehicleError);
    } finally {
      setVehicleLoading(false);
    }
  }, [handleApiError, user?.token, vehiclePagination.limit, vehiclePagination.offset, vehicleSearch, vehicleStatus]);

  const loadDrivers = useCallback(async () => {
    if (!user?.token) return;
    setDriverLoading(true);
    setDriverError(null);
    setIsForbidden(false);
    setModuleUnavailable(false);
    setModuleUnavailableReason(null);
    try {
      const response: PaginatedResponse<DriverDTO> = await fetchDrivers(user.token, {
        status: driverStatus || undefined,
        q: driverSearch.trim() || undefined,
        limit: driverPagination.limit,
        offset: driverPagination.offset,
      });
      setDriverState({
        items: response.items ?? [],
        total: response.total ?? 0,
      });
    } catch (error) {
      handleApiError(error, setDriverError);
    } finally {
      setDriverLoading(false);
    }
  }, [driverPagination.limit, driverPagination.offset, driverSearch, driverStatus, handleApiError, user?.token]);

  useEffect(() => {
    if (activeTab === "vehicles") {
      void loadVehicles();
    }
  }, [activeTab, loadVehicles]);

  useEffect(() => {
    if (activeTab === "drivers") {
      void loadDrivers();
    }
  }, [activeTab, loadDrivers]);

  const vehicleColumns: Column<VehicleDTO>[] = useMemo(
    () => [
      {
        key: "plate",
        title: t("logisticsFleet.vehicles.columns.plate"),
        render: (row) => row.plate ?? t("common.notAvailable"),
      },
      {
        key: "fuel",
        title: t("logisticsFleet.vehicles.columns.fuelType"),
        render: (row) => row.fuel_type ?? t("common.notAvailable"),
      },
      {
        key: "status",
        title: t("logisticsFleet.vehicles.columns.status"),
        render: (row) => (row.status ? <StatusBadge status={row.status} /> : t("common.notAvailable")),
      },
      {
        key: "makeModel",
        title: t("logisticsFleet.vehicles.columns.makeModel"),
        render: (row) => {
          const value = [row.make, row.model].filter(Boolean).join(" ");
          return value || t("common.notAvailable");
        },
      },
      {
        key: "vin",
        title: t("logisticsFleet.vehicles.columns.vin"),
        render: (row) => (row.vin ? <span title={row.vin}>{row.vin}</span> : t("common.notAvailable")),
      },
      {
        key: "actions",
        title: t("logisticsFleet.vehicles.columns.actions"),
        render: (row) => (
          <button type="button" className="ghost" onClick={() => setSelectedVehicle(row)}>
            {t("common.open")}
          </button>
        ),
      },
    ],
    [t],
  );

  const driverColumns: Column<DriverDTO>[] = useMemo(
    () => [
      {
        key: "name",
        title: t("logisticsFleet.drivers.columns.name"),
        render: (row) => row.name ?? t("common.notAvailable"),
      },
      {
        key: "phone",
        title: t("logisticsFleet.drivers.columns.phone"),
        render: (row) => row.phone ?? t("common.notAvailable"),
      },
      {
        key: "status",
        title: t("logisticsFleet.drivers.columns.status"),
        render: (row) => (row.status ? <StatusBadge status={row.status} /> : t("common.notAvailable")),
      },
      {
        key: "actions",
        title: t("logisticsFleet.drivers.columns.actions"),
        render: (row) => (
          <button type="button" className="ghost" onClick={() => setSelectedDriver(row)}>
            {t("common.open")}
          </button>
        ),
      },
    ],
    [t],
  );

  const vehiclePage = Math.floor(vehiclePagination.offset / vehiclePagination.limit) + 1;
  const vehiclePages = Math.max(1, Math.ceil(vehicleState.total / vehiclePagination.limit));
  const driverPage = Math.floor(driverPagination.offset / driverPagination.limit) + 1;
  const driverPages = Math.max(1, Math.ceil(driverState.total / driverPagination.limit));

  if (moduleUnavailable) {
    return <ModuleUnavailablePage title={t("logisticsFleet.title")} description={moduleUnavailableReason ?? t("logisticsFleet.errors.moduleDisabled")} />;
  }

  if (isForbidden) {
    return <AppForbiddenState message={t("logisticsFleet.errors.noPermission")} />;
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>{t("logisticsFleet.title")}</h1>
      </div>
      <div className="tabs">
        <button
          type="button"
          className={activeTab === "vehicles" ? "secondary" : "ghost"}
          onClick={() => setActiveTab("vehicles")}
        >
          {t("logisticsFleet.tabs.vehicles")}
        </button>
        <button
          type="button"
          className={activeTab === "drivers" ? "secondary" : "ghost"}
          onClick={() => setActiveTab("drivers")}
        >
          {t("logisticsFleet.tabs.drivers")}
        </button>
      </div>

      {activeTab === "vehicles" ? (
        <>
          <div className="filters">
            <div className="filter">
              <span className="label">{t("logisticsFleet.filters.status")}</span>
              <select
                value={vehicleStatus}
                onChange={(event) => {
                  setVehicleStatus(event.target.value);
                  setVehiclePagination((prev) => ({ ...prev, offset: 0 }));
                }}
              >
                <option value="">{t("logisticsFleet.statusAll")}</option>
                <option value="ACTIVE">{t("logisticsFleet.statusActive")}</option>
                <option value="INACTIVE">{t("logisticsFleet.statusInactive")}</option>
              </select>
            </div>
            <div className="filter filter--wide">
              <span className="label">{t("logisticsFleet.filters.search")}</span>
              <input
                value={vehicleSearch}
                onChange={(event) => {
                  setVehicleSearch(event.target.value);
                  setVehiclePagination((prev) => ({ ...prev, offset: 0 }));
                }}
                placeholder={t("logisticsFleet.vehicles.searchPlaceholder")}
              />
            </div>
          </div>
          <Table
            columns={vehicleColumns}
            data={vehicleState.items}
            loading={vehicleLoading}
            errorState={
              vehicleError
                ? {
                    title: t("logisticsFleet.errors.loadFailed"),
                    description: vehicleError,
                    actionLabel: t("errors.retry"),
                    actionOnClick: () => void loadVehicles(),
                  }
                : undefined
            }
            emptyState={{
              title: t("logisticsFleet.vehicles.emptyTitle"),
              description: t("logisticsFleet.vehicles.emptyDescription"),
            }}
          />
          <div className="pagination">
            <button
              type="button"
              className="secondary"
              onClick={() =>
                setVehiclePagination((prev) => ({ ...prev, offset: Math.max(0, prev.offset - prev.limit) }))
              }
              disabled={vehiclePagination.offset === 0 || vehicleLoading}
            >
              {t("common.back")}
            </button>
            <span className="muted">{t("logisticsFleet.pagination", { page: vehiclePage, total: vehiclePages })}</span>
            <button
              type="button"
              className="secondary"
              onClick={() =>
                setVehiclePagination((prev) => ({ ...prev, offset: prev.offset + prev.limit }))
              }
              disabled={vehiclePagination.offset + vehiclePagination.limit >= vehicleState.total || vehicleLoading}
            >
              {t("common.next")}
            </button>
          </div>
        </>
      ) : null}

      {activeTab === "drivers" ? (
        <>
          <div className="filters">
            <div className="filter">
              <span className="label">{t("logisticsFleet.filters.status")}</span>
              <select
                value={driverStatus}
                onChange={(event) => {
                  setDriverStatus(event.target.value);
                  setDriverPagination((prev) => ({ ...prev, offset: 0 }));
                }}
              >
                <option value="">{t("logisticsFleet.statusAll")}</option>
                <option value="ACTIVE">{t("logisticsFleet.statusActive")}</option>
                <option value="INACTIVE">{t("logisticsFleet.statusInactive")}</option>
              </select>
            </div>
            <div className="filter filter--wide">
              <span className="label">{t("logisticsFleet.filters.search")}</span>
              <input
                value={driverSearch}
                onChange={(event) => {
                  setDriverSearch(event.target.value);
                  setDriverPagination((prev) => ({ ...prev, offset: 0 }));
                }}
                placeholder={t("logisticsFleet.drivers.searchPlaceholder")}
              />
            </div>
          </div>
          <Table
            columns={driverColumns}
            data={driverState.items}
            loading={driverLoading}
            errorState={
              driverError
                ? {
                    title: t("logisticsFleet.errors.loadFailed"),
                    description: driverError,
                    actionLabel: t("errors.retry"),
                    actionOnClick: () => void loadDrivers(),
                  }
                : undefined
            }
            emptyState={{
              title: t("logisticsFleet.drivers.emptyTitle"),
              description: t("logisticsFleet.drivers.emptyDescription"),
            }}
          />
          <div className="pagination">
            <button
              type="button"
              className="secondary"
              onClick={() =>
                setDriverPagination((prev) => ({ ...prev, offset: Math.max(0, prev.offset - prev.limit) }))
              }
              disabled={driverPagination.offset === 0 || driverLoading}
            >
              {t("common.back")}
            </button>
            <span className="muted">{t("logisticsFleet.pagination", { page: driverPage, total: driverPages })}</span>
            <button
              type="button"
              className="secondary"
              onClick={() =>
                setDriverPagination((prev) => ({ ...prev, offset: prev.offset + prev.limit }))
              }
              disabled={driverPagination.offset + driverPagination.limit >= driverState.total || driverLoading}
            >
              {t("common.next")}
            </button>
          </div>
        </>
      ) : null}

      {selectedVehicle ? (
        <DetailModal
          title={t("logisticsFleet.vehicles.detailTitle")}
          closeLabel={t("actions.close")}
          metaLabel={t("logisticsFleet.metaTitle")}
          onClose={() => setSelectedVehicle(null)}
          meta={selectedVehicle.meta ?? null}
          fields={[
            { label: t("logisticsFleet.vehicles.columns.plate"), value: selectedVehicle.plate ?? t("common.notAvailable") },
            { label: t("logisticsFleet.vehicles.columns.vin"), value: selectedVehicle.vin ?? t("common.notAvailable") },
            { label: t("logisticsFleet.vehicles.columns.fuelType"), value: selectedVehicle.fuel_type ?? t("common.notAvailable") },
            {
              label: t("logisticsFleet.vehicles.columns.makeModel"),
              value: [selectedVehicle.make, selectedVehicle.model].filter(Boolean).join(" ") || t("common.notAvailable"),
            },
            {
              label: t("logisticsFleet.vehicles.columns.status"),
              value: selectedVehicle.status ?? t("common.notAvailable"),
            },
          ]}
        />
      ) : null}

      {selectedDriver ? (
        <DetailModal
          title={t("logisticsFleet.drivers.detailTitle")}
          closeLabel={t("actions.close")}
          metaLabel={t("logisticsFleet.metaTitle")}
          onClose={() => setSelectedDriver(null)}
          meta={selectedDriver.meta ?? null}
          fields={[
            { label: t("logisticsFleet.drivers.columns.name"), value: selectedDriver.name ?? t("common.notAvailable") },
            { label: t("logisticsFleet.drivers.columns.phone"), value: selectedDriver.phone ?? t("common.notAvailable") },
            { label: t("logisticsFleet.drivers.columns.status"), value: selectedDriver.status ?? t("common.notAvailable") },
          ]}
        />
      ) : null}
    </div>
  );
}
