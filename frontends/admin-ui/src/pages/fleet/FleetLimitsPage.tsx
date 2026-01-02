import { useCallback, useEffect, useMemo, useState } from "react";
import { listFleetLimits } from "../../api/fleet";
import { useAuth } from "../../auth/AuthContext";
import { DataTable, type DataColumn } from "../../components/common/DataTable";
import { EmptyState } from "../../components/common/EmptyState";
import { Loader } from "../../components/Loader/Loader";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import ForbiddenPage from "../ForbiddenPage";
import type { FleetLimit } from "../../types/fleet";
import { describeError } from "../../utils/apiErrors";
import { formatDateTime, formatQty, formatRub } from "../../utils/format";

const SCOPE_OPTIONS = [
  { value: "CLIENT", label: "Client" },
  { value: "CARD", label: "Card" },
  { value: "CARD_GROUP", label: "Card group" },
  { value: "VEHICLE", label: "Vehicle" },
  { value: "DRIVER", label: "Driver" },
];

const formatNumber = (value?: number | string | null, formatter?: (value: number) => string) => {
  if (value === undefined || value === null || value === "") return "—";
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
      setError({ title: "Не удалось загрузить лимиты", description: summary.message, details: summary.details });
    } finally {
      setLoading(false);
    }
  }, [accessToken, canQuery, scopeId, scopeType]);

  useEffect(() => {
    void loadLimits();
  }, [loadLimits]);

  const columns: DataColumn<FleetLimit>[] = [
    { key: "scope_type", title: "Scope", render: (row) => row.scope_type ?? "—" },
    { key: "scope_id", title: "Scope ID", render: (row) => row.scope_id ?? "—" },
    { key: "period", title: "Period", render: (row) => row.period ?? "—" },
    {
      key: "amount_limit",
      title: "Amount",
      render: (row) => formatNumber(row.amount_limit, formatRub),
    },
    {
      key: "volume_limit_liters",
      title: "Volume (L)",
      render: (row) => formatNumber(row.volume_limit_liters, formatQty),
    },
    {
      key: "active",
      title: "Status",
      render: (row) => (row.active === null || row.active === undefined ? "—" : <StatusBadge status={row.active ? "ACTIVE" : "INACTIVE"} />),
    },
    { key: "effective_from", title: "Effective", render: (row) => formatDateTime(row.effective_from) },
    { key: "created_at", title: "Created", render: (row) => formatDateTime(row.created_at) },
  ];

  if (isForbidden) {
    return <ForbiddenPage />;
  }

  if (unavailable) {
    return <div className="card">Fleet limits endpoint unavailable in this environment.</div>;
  }

  return (
    <div>
      <div className="page-header">
        <h1>Fleet · Limits</h1>
      </div>
      <div className="filters">
        <div className="filter">
          <span className="label">Scope type</span>
          <select value={scopeType} onChange={(event) => setScopeType(event.target.value)}>
            <option value="">Выберите</option>
            {SCOPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div className="filter">
          <span className="label">Scope ID</span>
          <input value={scopeId} onChange={(event) => setScopeId(event.target.value)} placeholder="UUID или ID" />
        </div>
        <div className="filter" style={{ alignSelf: "flex-end" }}>
          <button type="button" onClick={() => void loadLimits()} disabled={!canQuery || loading}>
            Обновить
          </button>
        </div>
      </div>
      {loading ? <Loader label="Загружаем лимиты" /> : null}
      {!canQuery && !loading ? (
        <EmptyState
          title="Выберите scope для просмотра лимитов"
          description="Укажите тип и идентификатор объекта, чтобы получить активные лимиты."
        />
      ) : (
        <DataTable
          data={limits}
          columns={columns}
          loading={false}
          errorState={error ? { title: error.title, description: error.description, details: error.details } : undefined}
          emptyState={{
            title: "Лимиты не найдены",
            description: "Для выбранного scope лимиты отсутствуют.",
          }}
        />
      )}
    </div>
  );
};

export default FleetLimitsPage;
