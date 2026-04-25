import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { listUsers, updateUser } from "../api/adminUsers";
import { UnauthorizedError } from "../api/http";
import { useAdmin } from "../admin/AdminContext";
import { useAuth } from "../auth/AuthContext";
import { hasAdminRole } from "../auth/roles";
import AdminWriteActionModal from "../components/admin/AdminWriteActionModal";
import { DataTable } from "../components/common/DataTable";
import { usersPageCopy } from "./operatorKeyPageCopy";
import { getAdminRoleEntry, type AdminUser } from "../types/users";

const formatRoleSummary = (roles: string[]) =>
  roles
    .map((role) => getAdminRoleEntry(role).label)
    .filter(Boolean)
    .join(", ");

export const UsersPage: React.FC = () => {
  const { accessToken, logout } = useAuth();
  const { profile } = useAdmin();
  const navigate = useNavigate();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingToggleUser, setPendingToggleUser] = useState<AdminUser | null>(null);
  const canManage = Boolean(profile?.permissions.access?.manage) && !profile?.read_only;

  const loadUsers = useCallback(() => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    listUsers(accessToken)
      .then((data) => setUsers(data))
      .catch((err) => {
        console.error(usersPageCopy.errors.loadLog, err);
        if (err instanceof UnauthorizedError) {
          logout();
          return;
        }
        setError(usersPageCopy.errors.load);
      })
      .finally(() => setLoading(false));
  }, [accessToken, logout]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const adminUsers = useMemo(() => users.filter((user) => hasAdminRole(user.roles)), [users]);

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return adminUsers;
    return adminUsers.filter((user) => {
      const roleSummary = formatRoleSummary(user.roles).toLowerCase();
      return (
        user.email.toLowerCase().includes(query) ||
        (user.full_name ?? "").toLowerCase().includes(query) ||
        roleSummary.includes(query)
      );
    });
  }, [adminUsers, search]);

  const filtersActive = search.trim().length > 0;

  const requestToggleActive = (item: AdminUser) => {
    if (!canManage) return;
    setPendingToggleUser(item);
  };

  const confirmToggleActive = async ({ reason, correlationId }: { reason: string; correlationId: string }) => {
    if (!accessToken || !canManage || !pendingToggleUser) return;
    try {
      const updated = await updateUser(accessToken, pendingToggleUser.id, {
        is_active: !pendingToggleUser.is_active,
        reason,
        correlation_id: correlationId,
      });
      setUsers((prev) => prev.map((user) => (user.id === updated.id ? updated : user)));
      setPendingToggleUser(null);
    } catch (err) {
      console.error(usersPageCopy.errors.updateLog, err);
      setError(usersPageCopy.errors.update);
    }
  };

  const columns = [
    { key: "email", title: usersPageCopy.columns.email, render: (item: AdminUser) => item.email },
    {
      key: "full_name",
      title: usersPageCopy.columns.fullName,
      render: (item: AdminUser) => item.full_name ?? usersPageCopy.values.fallback,
    },
    {
      key: "active",
      title: usersPageCopy.columns.status,
      render: (item: AdminUser) =>
        canManage ? (
          <button className="ghost neft-focus-ring" onClick={() => requestToggleActive(item)}>
            {item.is_active ? usersPageCopy.values.active : usersPageCopy.values.disabled}
          </button>
        ) : (
          <span className={`neft-chip ${item.is_active ? "neft-chip-success" : "neft-chip-muted"}`}>
            {item.is_active ? usersPageCopy.values.active : usersPageCopy.values.disabled}
          </span>
        ),
    },
    {
      key: "roles",
      title: usersPageCopy.columns.roles,
      render: (item: AdminUser) => formatRoleSummary(item.roles) || usersPageCopy.values.fallback,
    },
    {
      key: "created_at",
      title: usersPageCopy.columns.created,
      render: (item: AdminUser) =>
        item.created_at ? new Date(item.created_at).toLocaleString() : usersPageCopy.values.fallback,
    },
    ...(canManage
      ? [
          {
            key: "actions",
            title: usersPageCopy.columns.actions,
            render: (item: AdminUser) => (
              <div className="table-row-actions">
                <Link className="ghost" to={`/admins/${item.id}`}>
                  {usersPageCopy.actions.edit}
                </Link>
              </div>
            ),
          },
        ]
      : []),
  ];

  return (
    <div className="stack">
      <div className="page-header">
        <div>
          <h2>{usersPageCopy.header.title}</h2>
          <p className="muted">{usersPageCopy.header.description}</p>
        </div>
        {canManage ? (
          <Link to="/admins/new" className="button primary neft-btn-primary">
            {usersPageCopy.actions.add}
          </Link>
        ) : null}
      </div>

      <DataTable
        data={filtered}
        columns={columns}
        loading={loading}
        toolbar={
          <div className="table-toolbar">
            <div className="filters">
              <div className="filter filter--wide">
                <label className="label" htmlFor="admin-email-filter">
                  {usersPageCopy.actions.search}
                </label>
                <input
                  id="admin-email-filter"
                  className="neft-input neft-focus-ring"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="admin@neft.local"
                />
              </div>
            </div>
            <div className="toolbar-actions">
              <button
                type="button"
                className="button neft-btn-secondary"
                onClick={() => setSearch("")}
                disabled={!filtersActive}
              >
                {usersPageCopy.actions.reset}
              </button>
              <span className="muted small">
                {usersPageCopy.header.authHostHint}
              </span>
            </div>
          </div>
        }
        errorState={
          error
            ? {
                title: usersPageCopy.errors.loadTitle,
                description: error,
                actionLabel: usersPageCopy.actions.retry,
                actionOnClick: loadUsers,
              }
            : undefined
        }
        footer={
          <div className="table-footer__content muted">
            {usersPageCopy.footer.shown(filtered.length, adminUsers.length)}
          </div>
        }
        emptyState={{
          title: filtersActive ? usersPageCopy.empty.filteredTitle : usersPageCopy.empty.pristineTitle,
          description: filtersActive
            ? usersPageCopy.empty.filteredDescription
            : usersPageCopy.empty.pristineDescription,
          actionLabel: canManage
            ? filtersActive
              ? usersPageCopy.actions.resetFilters
              : usersPageCopy.actions.add
            : undefined,
          actionOnClick: canManage
            ? filtersActive
              ? () => setSearch("")
              : () => navigate("/admins/new")
            : undefined,
        }}
      />
      <AdminWriteActionModal
        isOpen={pendingToggleUser !== null}
        title={
          pendingToggleUser?.is_active
            ? usersPageCopy.modal.disableTitle
            : usersPageCopy.modal.enableTitle
        }
        onCancel={() => setPendingToggleUser(null)}
        onConfirm={confirmToggleActive}
      />
    </div>
  );
};

export default UsersPage;
