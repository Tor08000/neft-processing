import { useCallback, useEffect, useMemo, useState } from "react";
import { listFleetLimits } from "../../api/fleet";
import { useAuth } from "../../auth/AuthContext";
import { DataTable, type DataColumn } from "../../components/common/DataTable";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import ForbiddenPage from "../ForbiddenPage";
import type { FleetLimit } from "../../types/fleet";
import { describeError } from "../../utils/apiErrors";
import { formatDateTime, formatQty, formatRub } from "../../utils/format";
import { fleetLimitsPageCopy } from "./fleetPageCopy";

const SCOPE_OPTIONS = [
  { value: "CLIENT", label: "Client" },
  { value: "CARD", label: "Card" },
  { value: "CARD_GROUP", label: "Card group" },
  { value: "VEHICLE", label: "Vehicle" },
  { value: "DRIVER", label: "Driver" },
];

const formatNumber = (value?: number | string | null, formatter?: (value: number) => string) => {
  if (value === undefined || value === null || value === "") return fleetLimitsPageCopy.values.fallback;
  const parsed = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(parsed)) return String(value);
  return formatter ? formatter(parsed) : String(parsed);
};

export const FleetLimitsPage = () => {
  const { accessToken } = useAuth();
  const [limits, setLimits] = useState<FleetLimit[]>([]);
  const [scopeType, setScopeType] = useState("");
  const [scopeId, setScopeId] = useState("");
  const [loading, setLoading] = useState(false);
  const [isForbidden, setIsForbidden] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [error, setError] = useState<{ title: string; description?: string; details?: string } | null>(null);

  const canQuery = useMemo(() => Boolean(scopeType && scopeId.trim()), [scopeType, scopeId]);

  const loadLimits = useCallback(async () => {
    if (!accessToken || !canQuery) {
      setLimits([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setIsForbidden(false);
    setUnavailable(false);
    setError(null);
    try {
      const response = await listFleetLimits(accessToken, { scope_type: scopeType, scope_id: scopeId.trim() });
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      setLimits(response.items);
    } catch (err) {
      const summary = describeError(err);
      if (summary.isForbidden) {
        setIsForbidden(true);
        return;
      }
      setError({ title: fleetLimitsPageCopy.errors.load, description: summary.message, details: summary.details });
    } finally {
      setLoading(false);
    }
  }, [accessToken, canQuery, scopeId, scopeType]);

  useEffect(() => {
    void loadLimits();
  }, [loadLimits]);

  const columns: DataColumn<FleetLimit>[] = [
    { key: "scope_type", title: fleetLimitsPageCopy.columns.scope, render: (row) => row.scope_type ?? fleetLimitsPageCopy.values.fallback },
    { key: "scope_id", title: fleetLimitsPageCopy.columns.scopeId, render: (row) => row.scope_id ?? fleetLimitsPageCopy.values.fallback },
    { key: "period", title: fleetLimitsPageCopy.columns.period, render: (row) => row.period ?? fleetLimitsPageCopy.values.fallback },
    {
      key: "amount_limit",
      title: fleetLimitsPageCopy.columns.amount,
      render: (row) => formatNumber(row.amount_limit, formatRub),
    },
    {
      key: "volume_limit_liters",
      title: fleetLimitsPageCopy.columns.volume,
      render: (row) => formatNumber(row.volume_limit_liters, formatQty),
    },
    {
      key: "active",
      title: fleetLimitsPageCopy.columns.status,
      render: (row) =>
        row.active === null || row.active === undefined ? fleetLimitsPageCopy.values.fallback : <StatusBadge status={row.active ? "ACTIVE" : "INACTIVE"} />,
    },
    { key: "effective_from", title: fleetLimitsPageCopy.columns.effective, render: (row) => formatDateTime(row.effective_from) },
    { key: "created_at", title: fleetLimitsPageCopy.columns.created, render: (row) => formatDateTime(row.created_at) },
  ];

  if (isForbidden) {
    return <ForbiddenPage />;
  }

  if (unavailable) {
    return <div className="card">{fleetLimitsPageCopy.unavailable}</div>;
  }

  return (
    <div>
      <div className="page-header">
        <h1>{fleetLimitsPageCopy.title}</h1>
      </div>
      <DataTable
        data={limits}
        columns={columns}
        loading={loading}
        toolbar={
          <div className="table-toolbar">
            <div className="filters">
              <div className="filter">
                <span className="label">{fleetLimitsPageCopy.filters.scopeType}</span>
                <select value={scopeType} onChange={(event) => setScopeType(event.target.value)}>
                  <option value="">{fleetLimitsPageCopy.filters.select}</option>
                  {SCOPE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="filter">
                <span className="label">{fleetLimitsPageCopy.filters.scopeId}</span>
                <input
                  value={scopeId}
                  onChange={(event) => setScopeId(event.target.value)}
                  placeholder={fleetLimitsPageCopy.filters.scopePlaceholder}
                />
              </div>
            </div>
            <div className="toolbar-actions">
              <button type="button" className="button secondary" onClick={() => void loadLimits()} disabled={!canQuery || loading}>
                {fleetLimitsPageCopy.actions.refresh}
              </button>
            </div>
          </div>
        }
        errorState={
          error
            ? {
                title: error.title,
                description: error.description,
                details: error.details,
                actionLabel: fleetLimitsPageCopy.actions.retry,
                actionOnClick: () => void loadLimits(),
              }
            : undefined
        }
        footer={<div className="table-footer__content muted">{fleetLimitsPageCopy.footer.rows(canQuery ? limits.length : 0)}</div>}
        emptyState={{
          title: canQuery ? fleetLimitsPageCopy.empty.noLimitsTitle : fleetLimitsPageCopy.empty.missingScopeTitle,
          description: canQuery
            ? fleetLimitsPageCopy.empty.noLimitsDescription
            : fleetLimitsPageCopy.empty.missingScopeDescription,
        }}
      />
    </div>
  );
};

export default FleetLimitsPage;
