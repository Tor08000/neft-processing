import React, { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { listUsers, updateUser } from "../api/adminUsers";
import { fetchAuditFeed } from "../api/audit";
import { useAdmin } from "../admin/AdminContext";
import { useAuth } from "../auth/AuthContext";
import { hasAdminRole } from "../auth/roles";
import AdminWriteActionModal from "../components/admin/AdminWriteActionModal";
import { Loader } from "../components/Loader/Loader";
import { editUserPageCopy } from "./operatorKeyPageCopy";
import {
  ADMIN_ROLE_CATALOG,
  getAdminRoleEntry,
  type AdminRoleCatalogEntry,
  type AdminUser,
} from "../types/users";

const buildRoleOptions = (roles: string[]): AdminRoleCatalogEntry[] => {
  const existing = new Map(ADMIN_ROLE_CATALOG.map((entry) => [entry.code, entry]));
  roles.forEach((role) => {
    if (!existing.has(role)) {
      existing.set(role, getAdminRoleEntry(role));
    }
  });
  return [
    ...ADMIN_ROLE_CATALOG,
    ...[...existing.values()].filter((entry) => !ADMIN_ROLE_CATALOG.some((base) => base.code === entry.code)),
  ];
};

export const EditUserPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { accessToken } = useAuth();
  const { profile } = useAdmin();
  const navigate = useNavigate();
  const [current, setCurrent] = useState<AdminUser | null>(null);
  const [fullName, setFullName] = useState("");
  const [roles, setRoles] = useState<string[]>([]);
  const [isActive, setIsActive] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingUpdate, setPendingUpdate] = useState<{
    full_name: string;
    is_active: boolean;
    roles: string[];
  } | null>(null);

  useEffect(() => {
    if (!id || !accessToken) return;
    listUsers(accessToken)
      .then((users) => {
        const found = users.find((user) => user.id === id);
        if (!found) {
          setError(editUserPageCopy.errors.notFound);
          return;
        }
        if (!hasAdminRole(found.roles)) {
          setError(editUserPageCopy.errors.nonAdmin);
          return;
        }
        setCurrent(found);
        setFullName(found.full_name ?? "");
        setRoles(found.roles);
        setIsActive(found.is_active);
      })
      .catch((err) => {
        console.error(editUserPageCopy.errors.loadLog, err);
        setError(editUserPageCopy.errors.load);
      });
  }, [id, accessToken]);

  const toggleRole = (role: string) => {
    setRoles((currentRoles) =>
      currentRoles.includes(role) ? currentRoles.filter((item) => item !== role) : [...currentRoles, role],
    );
  };

  const roleOptions = useMemo(() => buildRoleOptions(roles), [roles]);
  const canSave = useMemo(() => Boolean(current && roles.length > 0), [current, roles]);
  const canReadAudit = Boolean(profile?.permissions.audit.read);

  const { data: auditFeed, isLoading: auditLoading } = useQuery({
    queryKey: ["admin-user-audit-preview", id],
    queryFn: () =>
      fetchAuditFeed(accessToken ?? "", {
        entity_type: "admin_user",
        entity_id: id ?? "",
        limit: 5,
      }),
    enabled: Boolean(accessToken && id && canReadAudit),
    staleTime: 20_000,
  });

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!accessToken || !current) return;
    setError(null);
    setPendingUpdate({
      full_name: fullName,
      is_active: isActive,
      roles,
    });
  };

  const confirmUpdate = async ({ reason, correlationId }: { reason: string; correlationId: string }) => {
    if (!accessToken || !current || !pendingUpdate) return;
    try {
      const updated = await updateUser(accessToken, current.id, {
        ...pendingUpdate,
        reason,
        correlation_id: correlationId,
      });
      setCurrent(updated);
      setPendingUpdate(null);
      navigate("/admins");
    } catch (err) {
      console.error(editUserPageCopy.errors.updateLog, err);
      setError(editUserPageCopy.errors.update);
    }
  };

  if (!current) {
    return <div className="card">{error ?? editUserPageCopy.errors.loading}</div>;
  }

  return (
    <div className="card">
      <h2>{editUserPageCopy.header.title}</h2>
      <p className="muted">{current.email}</p>
      {error ? <div className="error-text">{error}</div> : null}
      <form className="form-grid" onSubmit={handleSubmit}>
        <label className="label">{editUserPageCopy.labels.fullName}</label>
        <input type="text" value={fullName} onChange={(event) => setFullName(event.target.value)} />

        <label className="label">{editUserPageCopy.labels.active}</label>
        <label className="checkbox">
          <input type="checkbox" checked={isActive} onChange={(event) => setIsActive(event.target.checked)} />{" "}
          {editUserPageCopy.labels.active}
        </label>

        <label className="label">{editUserPageCopy.labels.roles}</label>
        <div className="stack">
          {roleOptions.map((role) => (
            <label key={role.code} className="checkbox" style={{ display: "grid", gap: 4 }}>
              <span>
                <input type="checkbox" checked={roles.includes(role.code)} onChange={() => toggleRole(role.code)} />{" "}
                {role.label}
              </span>
              <span className="muted small">{role.description}</span>
            </label>
          ))}
        </div>

        <div style={{ display: "flex", gap: 12 }}>
          <button type="submit" disabled={!canSave}>
            {editUserPageCopy.actions.save}
          </button>
          <button type="button" className="ghost" onClick={() => navigate(-1)}>
            {editUserPageCopy.actions.cancel}
          </button>
        </div>
      </form>
      {canReadAudit && current ? (
        <div className="card" style={{ marginTop: 16 }}>
          <div style={{ display: "flex", gap: 12, alignItems: "center", justifyContent: "space-between", flexWrap: "wrap" }}>
            <div>
              <h3 style={{ margin: 0 }}>{editUserPageCopy.audit.title}</h3>
              <p className="muted" style={{ margin: "4px 0 0" }}>
                {editUserPageCopy.audit.description}
              </p>
            </div>
            <Link to={`/audit?entity_type=admin_user&entity_id=${encodeURIComponent(current.id)}`}>
              {editUserPageCopy.audit.openFull}
            </Link>
          </div>
          {auditLoading ? <Loader label={editUserPageCopy.audit.loading} /> : null}
          {!auditLoading && (auditFeed?.items?.length ?? 0) === 0 ? (
            <div className="muted" style={{ marginTop: 12 }}>{editUserPageCopy.audit.empty}</div>
          ) : null}
          {auditFeed?.items?.length ? (
            <div style={{ display: "grid", gap: 12, marginTop: 12 }}>
              {auditFeed.items.map((event) => (
                <div key={event.id ?? `${event.ts}-${event.correlation_id ?? "audit"}`} className="audit-block">
                  <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                    <strong>{event.title ?? event.action ?? event.type ?? editUserPageCopy.audit.fallbackTitle}</strong>
                    {event.ts ? <span className="muted">{event.ts}</span> : null}
                    {event.correlation_id ? (
                      <Link to={`/audit/${encodeURIComponent(event.correlation_id)}`}>{editUserPageCopy.audit.chain}</Link>
                    ) : null}
                  </div>
                  {event.reason ? (
                    <div className="audit-item__reason">
                      {editUserPageCopy.audit.reasonLabel}: {event.reason}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
      <AdminWriteActionModal
        isOpen={pendingUpdate !== null}
        title={editUserPageCopy.modal.title}
        onCancel={() => setPendingUpdate(null)}
        onConfirm={confirmUpdate}
      />
    </div>
  );
};

export default EditUserPage;
