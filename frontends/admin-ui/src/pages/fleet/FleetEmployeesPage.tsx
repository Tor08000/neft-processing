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
      setError({ title: "Не удалось загрузить сотрудников", description: summary.message, details: summary.details });
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    void loadEmployees();
  }, [loadEmployees]);

  const columns: DataColumn<FleetEmployee>[] = [
    { key: "email", title: "Email", render: (row) => row.email },
    { key: "status", title: "Status", render: (row) => (row.status ? <StatusBadge status={row.status} /> : "—") },
    { key: "created_at", title: "Created", render: (row) => formatDateTime(row.created_at) },
  ];

  if (loading) {
    return <Loader label="Загружаем сотрудников" />;
  }

  if (isForbidden) {
    return <ForbiddenPage />;
  }

  if (unavailable) {
    return <div className="card">Fleet employees endpoint unavailable in this environment.</div>;
  }

  return (
    <div>
      <div className="page-header">
        <h1>Fleet · Employees</h1>
      </div>
      <DataTable
        data={employees}
        columns={columns}
        loading={false}
        errorState={error ? { title: error.title, description: error.description, details: error.details } : undefined}
        emptyState={{
          title: "Сотрудники не найдены",
          description: "Пригласите сотрудников в клиентском кабинете, чтобы настроить роли доступа.",
        }}
      />
    </div>
  );
};

export default FleetEmployeesPage;
