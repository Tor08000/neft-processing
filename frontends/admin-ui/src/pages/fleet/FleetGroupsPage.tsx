import { useCallback, useEffect, useState } from "react";
import { listFleetGroups } from "../../api/fleet";
import { useAuth } from "../../auth/AuthContext";
import { DataTable, type DataColumn } from "../../components/common/DataTable";
import { Loader } from "../../components/Loader/Loader";
import ForbiddenPage from "../ForbiddenPage";
import type { FleetGroup } from "../../types/fleet";
import { describeError } from "../../utils/apiErrors";
import { formatDateTime } from "../../utils/format";

export const FleetGroupsPage = () => {
  const { accessToken } = useAuth();
  const [groups, setGroups] = useState<FleetGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [isForbidden, setIsForbidden] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [error, setError] = useState<{ title: string; description?: string; details?: string } | null>(null);

  const loadGroups = useCallback(async () => {
    if (!accessToken) return;
    setLoading(true);
    setIsForbidden(false);
    setUnavailable(false);
    setError(null);
    try {
      const response = await listFleetGroups(accessToken);
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      setGroups(response.items);
    } catch (err) {
      const summary = describeError(err);
      if (summary.isForbidden) {
        setIsForbidden(true);
        return;
      }
      setError({ title: "Не удалось загрузить группы", description: summary.message, details: summary.details });
    } finally {
      setLoading(false);
    }
  }, [accessToken]);

  useEffect(() => {
    void loadGroups();
  }, [loadGroups]);

  const columns: DataColumn<FleetGroup>[] = [
    { key: "name", title: "Group", render: (row) => row.name },
    { key: "description", title: "Description", render: (row) => row.description ?? "—" },
    { key: "created_at", title: "Created", render: (row) => formatDateTime(row.created_at) },
  ];

  if (loading) {
    return <Loader label="Загружаем группы" />;
  }

  if (isForbidden) {
    return <ForbiddenPage />;
  }

  if (unavailable) {
    return <div className="card">Fleet groups endpoint unavailable in this environment.</div>;
  }

  return (
    <div>
      <div className="page-header">
        <h1>Fleet · Groups</h1>
      </div>
      <DataTable
        data={groups}
        columns={columns}
        loading={false}
        errorState={error ? { title: error.title, description: error.description, details: error.details } : undefined}
        emptyState={{
          title: "Группы не найдены",
          description: "Добавьте группы в клиентском кабинете, чтобы управлять доступом к картам.",
        }}
      />
    </div>
  );
};

export default FleetGroupsPage;
