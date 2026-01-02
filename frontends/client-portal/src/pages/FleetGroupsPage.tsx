import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listGroups, createGroup } from "../api/fleet";
import type { FleetGroup } from "../types/fleet";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import { Table } from "../components/common/Table";
import type { Column } from "../components/common/Table";
import { RoleBadge } from "../components/RoleBadge";
import { AppForbiddenState } from "../components/states";
import { FleetUnavailableState } from "../components/FleetUnavailableState";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";
import { ApiError } from "../api/http";
import { formatDateTime } from "../utils/format";
import { canManageFleetGroups, deriveGroupRole } from "../utils/fleetPermissions";

export function FleetGroupsPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const { toast, showToast } = useToast();
  const [groups, setGroups] = useState<FleetGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isForbidden, setIsForbidden] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const canManage = canManageFleetGroups(user);

  const loadGroups = useCallback(async () => {
    if (!user?.token) return;
    setLoading(true);
    setError(null);
    setIsForbidden(false);
    setUnavailable(false);
    try {
      const response = await listGroups(user.token);
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      setGroups(response.items);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setIsForbidden(true);
        return;
      }
      setError(err instanceof Error ? err.message : t("fleet.errors.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [t, user?.token]);

  useEffect(() => {
    void loadGroups();
  }, [loadGroups]);

  const handleOpenCreate = () => {
    setName("");
    setDescription("");
    setFormError(null);
    setShowCreateModal(true);
  };

  const handleCreateGroup = async () => {
    if (!user?.token) return;
    if (!name.trim()) {
      setFormError(t("fleet.groups.nameRequired"));
      return;
    }
    setFormError(null);
    try {
      const response = await createGroup(user.token, { name: name.trim(), description: description.trim() || undefined });
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      if (response.item) {
        setGroups((prev) => [response.item!, ...prev]);
        showToast({ kind: "success", text: t("fleet.groups.created") });
        setShowCreateModal(false);
      }
    } catch (err) {
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleet.errors.actionFailed") });
    }
  };

  const columns: Column<FleetGroup>[] = [
    { key: "name", title: t("fleet.groups.name"), render: (row) => row.name },
    {
      key: "cards",
      title: t("fleet.groups.cardsCount"),
      render: (row) => String(row.cards_count ?? row.cards?.length ?? 0),
    },
    {
      key: "role",
      title: t("fleet.groups.myRole"),
      render: (row) => <RoleBadge role={deriveGroupRole(user, row.my_role)} />,
    },
    {
      key: "created",
      title: t("fleet.groups.created"),
      render: (row) => (row.created_at ? formatDateTime(row.created_at) : t("common.notAvailable")),
    },
    {
      key: "actions",
      title: t("fleet.groups.actions"),
      render: (row) => (
        <Link className="ghost" to={`/fleet/groups/${row.id}`}>
          {t("common.open")}
        </Link>
      ),
    },
  ];

  if (loading) {
    return (
      <div className="page">
        <div className="page-header">
          <h1>{t("fleet.groups.title")}</h1>
        </div>
        <Table columns={columns} data={[]} loading />
      </div>
    );
  }

  if (isForbidden) {
    return <AppForbiddenState message={t("fleet.errors.noPermission")} />;
  }

  if (unavailable) {
    return <FleetUnavailableState />;
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>{t("fleet.groups.title")}</h1>
        <div className="actions">
          {canManage ? (
            <button type="button" className="primary" onClick={handleOpenCreate}>
              {t("fleet.groups.create")}
            </button>
          ) : null}
          <button type="button" className="secondary" onClick={() => void loadGroups()}>
            {t("actions.refresh")}
          </button>
        </div>
      </div>
      {error ? <div className="card state">{error}</div> : null}
      <Table
        columns={columns}
        data={groups}
        emptyState={{ title: t("fleet.groups.emptyTitle"), description: t("fleet.groups.emptyDescription") }}
      />
      {showCreateModal ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-card">
            <h2>{t("fleet.groups.createTitle")}</h2>
            <div className="form-grid">
              <label className="form-field">
                <span>{t("fleet.groups.name")}</span>
                <input value={name} onChange={(event) => setName(event.target.value)} />
              </label>
              <label className="form-field">
                <span>{t("fleet.groups.description")}</span>
                <input value={description} onChange={(event) => setDescription(event.target.value)} />
              </label>
            </div>
            {formError ? <div className="error-text">{formError}</div> : null}
            <div className="actions">
              <button type="button" className="ghost" onClick={() => setShowCreateModal(false)}>
                {t("actions.comeBackLater")}
              </button>
              <button type="button" className="primary" onClick={() => void handleCreateGroup()}>
                {t("fleet.groups.submit")}
              </button>
            </div>
          </div>
        </div>
      ) : null}
      <Toast toast={toast} />
    </div>
  );
}
