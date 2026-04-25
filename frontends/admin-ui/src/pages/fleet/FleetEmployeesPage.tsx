import { useCallback, useEffect, useState } from "react";
import { listFleetEmployees } from "../../api/fleet";
import { useAuth } from "../../auth/AuthContext";
import { DataTable, type DataColumn } from "../../components/common/DataTable";
import { Loader } from "../../components/Loader/Loader";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import ForbiddenPage from "../ForbiddenPage";
import type { FleetEmployee } from "../../types/fleet";
import { describeError } from "../../utils/apiErrors";
import { formatDateTime } from "../../utils/format";
import { fleetEmployeesPageCopy } from "./fleetPageCopy";

export const FleetEmployeesPage = () => {
  const { accessToken } = useAuth();
  const [employees, setEmployees] = useState<FleetEmployee[]>([]);
  const [loading, setLoading] = useState(true);
  const [isForbidden, setIsForbidden] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [error, setError] = useState<{ title: string; description?: string; details?: string } | null>(null);

  const loadEmployees = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    setIsForbidden(false);
    setUnavailable(false);
    setError(null);
    try {
      const response = await listFleetEmployees(accessToken);
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      setEmployees(response.items);
    } catch (err) {
      const summary = describeError(err);
      if (summary.isForbidden) {
        setIsForbidden(true);
        return;
      }
      setError({ title: fleetEmployeesPageCopy.errors.load, description: summary.message, details: summary.details });
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    void loadEmployees();
  }, [loadEmployees]);

  const columns: DataColumn<FleetEmployee>[] = [
    { key: "email", title: fleetEmployeesPageCopy.columns.email, render: (row) => row.email },
    {
      key: "status",
      title: fleetEmployeesPageCopy.columns.status,
      render: (row) => (row.status ? <StatusBadge status={row.status} /> : fleetEmployeesPageCopy.values.fallback),
    },
    { key: "created_at", title: fleetEmployeesPageCopy.columns.created, render: (row) => formatDateTime(row.created_at) },
  ];

  if (loading) {
    return <Loader label={fleetEmployeesPageCopy.loading} />;
  }

  if (isForbidden) {
    return <ForbiddenPage />;
  }

  if (unavailable) {
    return <div className="card">{fleetEmployeesPageCopy.unavailable}</div>;
  }

  return (
    <div>
      <div className="page-header">
        <h1>{fleetEmployeesPageCopy.title}</h1>
      </div>
      <DataTable
        data={employees}
        columns={columns}
        loading={false}
        errorState={error ? { title: error.title, description: error.description, details: error.details } : undefined}
        emptyState={{
          title: fleetEmployeesPageCopy.empty.title,
          description: fleetEmployeesPageCopy.empty.description,
        }}
      />
    </div>
  );
};

export default FleetEmployeesPage;
