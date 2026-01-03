import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { listPolicies, type PolicyIndexItem, type PolicyStatus, type PolicyType } from "../api/policies";
import { useAuth } from "../auth/AuthContext";
import { DataTable, type DataColumn } from "../components/common/DataTable";
import { EmptyState as BrandEmptyState, StatusPill } from "../../../shared/brand/components";
import ForbiddenPage from "./ForbiddenPage";
import { describeError } from "../utils/apiErrors";
import { formatDateTime } from "../utils/format";

const TYPE_OPTIONS: { value: PolicyType | ""; label: string }[] = [
  { value: "", label: "All" },
  { value: "fleet", label: "Fleet" },
  { value: "finance", label: "Finance" },
  { value: "marketplace", label: "Marketplace" },
];

const STATUS_OPTIONS: { value: PolicyStatus | ""; label: string }[] = [
  { value: "", label: "All" },
  { value: "enabled", label: "Enabled" },
  { value: "disabled", label: "Disabled" },
];

const statusTone = (status: PolicyStatus) => (status === "enabled" ? "success" : "neutral");

export const PolicyCenterPage = () => {
  const { accessToken } = useAuth();
  const [policies, setPolicies] = useState<PolicyIndexItem[]>([]);
  const [typeFilter, setTypeFilter] = useState<PolicyType | "">("");
  const [statusFilter, setStatusFilter] = useState<PolicyStatus | "">("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [isForbidden, setIsForbidden] = useState(false);
  const [error, setError] = useState<{ title: string; description?: string; details?: string } | null>(null);

  const loadPolicies = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    setIsForbidden(false);
    setError(null);
    try {
      const response = await listPolicies(accessToken, {
        type: typeFilter || undefined,
        status: statusFilter || undefined,
        q: query || undefined,
      });
      setPolicies(response.items);
    } catch (err) {
      const summary = describeError(err);
      if (summary.isForbidden) {
        setIsForbidden(true);
        return;
      }
      setError({ title: "Не удалось загрузить политики", description: summary.message, details: summary.details });
    } finally {
      setLoading(false);
    }
  }, [accessToken, query, statusFilter, typeFilter]);

  useEffect(() => {
    void loadPolicies();
  }, [loadPolicies]);

  const columns = useMemo<DataColumn<PolicyIndexItem>[]>(
    () => [
      { key: "title", title: "Title", render: (row) => row.title },
      { key: "type", title: "Type", render: (row) => row.type.toUpperCase() },
      {
        key: "status",
        title: "Status",
        render: (row) => <StatusPill tone={statusTone(row.status)}>{row.status}</StatusPill>,
      },
      {
        key: "actions",
        title: "Actions",
        render: (row) => (
          <div className="pill-list">
            {row.actions.length ? (
              row.actions.map((action) => (
                <span key={action} className="pill pill--outline">
                  {action}
                </span>
              ))
            ) : (
              <span className="pill pill--neutral">No actions</span>
            )}
          </div>
        ),
      },
      {
        key: "updated",
        title: "Updated",
        render: (row) => (row.updated_at ? formatDateTime(row.updated_at) : "—"),
      },
      {
        key: "view",
        title: "View",
        render: (row) => (
          <Link className="button" to={`/policies/${row.type}/${row.id}`}>
            Open
          </Link>
        ),
      },
    ],
    [],
  );

  if (isForbidden) {
    return <ForbiddenPage />;
  }

  return (
    <div className="policy-center">
      <div className="page-header">
        <h1>Policy Center</h1>
        <p className="muted">Unified view across fleet, finance, and marketplace policy engines.</p>
      </div>
      <div className="filters">
        <div className="filter">
          <span className="label">Type</span>
          <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value as PolicyType | "")}>
            {TYPE_OPTIONS.map((option) => (
              <option key={option.value || "all"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div className="filter">
          <span className="label">Status</span>
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as PolicyStatus | "")}>
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value || "all"} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div className="filter filter--grow">
          <span className="label">Search</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="title / id / action"
          />
        </div>
        <div className="filter" style={{ alignSelf: "flex-end" }}>
          <button type="button" onClick={() => void loadPolicies()} disabled={loading}>
            Refresh
          </button>
        </div>
      </div>
      {error ? (
        <div className="card card--error">
          <strong>{error.title}</strong>
          <div>{error.description}</div>
        </div>
      ) : null}
      {loading ? (
        <DataTable data={[]} columns={columns} loading />
      ) : policies.length ? (
        <DataTable data={policies} columns={columns} />
      ) : (
        <BrandEmptyState
          title="No policies found"
          description={
            typeFilter
              ? "The selected type is not implemented yet or has no policies."
              : "There are no policies available for the current filters."
          }
        />
      )}
    </div>
  );
};

export default PolicyCenterPage;
