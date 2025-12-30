import { useEffect, useMemo, useState } from "react";
import { createClientUser, disableClientUser, fetchClientUsers, updateClientUserRole } from "../api/controls";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { ConfirmActionModal } from "../components/ConfirmActionModal";
import { AppEmptyState, AppErrorState, AppForbiddenState, AppLoadingState } from "../components/states";
import type { ClientUserSummary } from "../types/controls";
import { formatDateTime } from "../utils/format";
import { hasAnyRole } from "../utils/roles";

interface PageErrorState {
  message: string;
  status?: number;
  correlationId?: string | null;
}

interface ActionNotice {
  title: string;
  description?: string;
  correlationId?: string | null;
}

const roleLabels: Record<string, string> = {
  CLIENT_OWNER: "CLIENT_OWNER",
  CLIENT_ADMIN: "CLIENT_ADMIN",
  CLIENT_USER: "CLIENT_USER",
};

export function ClientUsersPage() {
  const { user } = useAuth();
  const [users, setUsers] = useState<ClientUserSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<PageErrorState | null>(null);
  const [notice, setNotice] = useState<ActionNotice | null>(null);

  const [isAddOpen, setIsAddOpen] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [newRole, setNewRole] = useState("CLIENT_USER");
  const [addError, setAddError] = useState<PageErrorState | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [roleUser, setRoleUser] = useState<ClientUserSummary | null>(null);
  const [roleValue, setRoleValue] = useState("CLIENT_USER");
  const [roleError, setRoleError] = useState<PageErrorState | null>(null);

  const [disableUser, setDisableUser] = useState<ClientUserSummary | null>(null);
  const [disableError, setDisableError] = useState<PageErrorState | null>(null);

  const canManage = hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ADMIN"]);

  const loadUsers = () => {
    if (!user) return;
    setIsLoading(true);
    setError(null);
    fetchClientUsers(user)
      .then((resp) => setUsers(resp.items ?? []))
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setError({ message: err.message, status: err.status, correlationId: err.correlationId });
          return;
        }
        setError({ message: err instanceof Error ? err.message : "Не удалось загрузить пользователей" });
      })
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    loadUsers();
  }, [user]);

  const activeUsers = useMemo(() => users.filter((item) => item.status !== "disabled"), [users]);

  if (!user) {
    return <AppForbiddenState message="Требуется авторизация." />;
  }

  if (isLoading) {
    return <AppLoadingState label="Загружаем пользователей..." />;
  }

  if (error) {
    return (
      <AppErrorState
        message={error.message}
        status={error.status}
        correlationId={error.correlationId}
        onRetry={loadUsers}
      />
    );
  }

  const openAddModal = () => {
    setIsAddOpen(true);
    setNewEmail("");
    setNewRole("CLIENT_USER");
    setAddError(null);
  };

  const handleAddUser = async () => {
    if (!user) return;
    setIsSubmitting(true);
    setAddError(null);
    try {
      const response = await createClientUser(user, { email: newEmail, role: newRole });
      setNotice({
        title: "Пользователь добавлен",
        description: newEmail,
        correlationId: response.correlationId,
      });
      setIsAddOpen(false);
      loadUsers();
    } catch (err) {
      if (err instanceof ApiError) {
        setAddError({ message: err.message, status: err.status, correlationId: err.correlationId });
      } else {
        setAddError({ message: err instanceof Error ? err.message : "Не удалось добавить пользователя" });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRoleSubmit = async () => {
    if (!user || !roleUser) return;
    setIsSubmitting(true);
    setRoleError(null);
    try {
      const response = await updateClientUserRole(user, roleUser.id, { role: roleValue });
      setNotice({
        title: "Роль обновлена",
        description: `${roleUser.email} → ${roleValue}`,
        correlationId: response.correlationId,
      });
      setRoleUser(null);
      loadUsers();
    } catch (err) {
      if (err instanceof ApiError) {
        setRoleError({ message: err.message, status: err.status, correlationId: err.correlationId });
      } else {
        setRoleError({ message: err instanceof Error ? err.message : "Не удалось изменить роль" });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDisable = async () => {
    if (!user || !disableUser) return;
    setIsSubmitting(true);
    setDisableError(null);
    try {
      const response = await disableClientUser(user, disableUser.id);
      setNotice({
        title: "Пользователь отключён",
        description: disableUser.email,
        correlationId: response.correlationId,
      });
      setDisableUser(null);
      loadUsers();
    } catch (err) {
      if (err instanceof ApiError) {
        setDisableError({ message: err.message, status: err.status, correlationId: err.correlationId });
      } else {
        setDisableError({ message: err instanceof Error ? err.message : "Не удалось отключить пользователя" });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="stack">
      <section className="card">
        <div className="card__header">
          <div>
            <h3>Пользователи</h3>
            <p className="muted">Управляйте ролями и доступами пользователей.</p>
          </div>
          <button type="button" className="primary" onClick={openAddModal} disabled={!canManage}>
            Добавить пользователя
          </button>
        </div>
        {!canManage ? <div className="muted small">Действия доступны только CLIENT_OWNER/CLIENT_ADMIN.</div> : null}
        {notice ? (
          <div className="notice">
            <strong>{notice.title}</strong>
            {notice.description ? <div className="muted small">{notice.description}</div> : null}
            {notice.correlationId ? <div className="muted small">Correlation ID: {notice.correlationId}</div> : null}
          </div>
        ) : null}
      </section>

      <section className="card">
        {users.length === 0 ? (
          <AppEmptyState title="Пользователей нет" description="Добавьте первых пользователей в кабинет." />
        ) : (
          <>
            <table className="table">
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Роль</th>
                  <th>Статус</th>
                  <th>Last login</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {users.map((item) => (
                  <tr key={item.id}>
                    <td>{item.email}</td>
                    <td>{roleLabels[item.role] ?? item.role}</td>
                    <td>{item.status ?? "—"}</td>
                    <td>{item.last_login ? formatDateTime(item.last_login) : "—"}</td>
                    <td>
                      <div className="actions">
                        <button
                          type="button"
                          className="secondary"
                          disabled={!canManage}
                          onClick={() => {
                            setRoleUser(item);
                            setRoleValue(item.role);
                            setRoleError(null);
                          }}
                        >
                          Изменить роль
                        </button>
                        <button
                          type="button"
                          className="ghost"
                          disabled={!canManage || item.status === "disabled"}
                          onClick={() => {
                            setDisableUser(item);
                            setDisableError(null);
                          }}
                        >
                          Отключить
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="table-footer muted small">Активных пользователей: {activeUsers.length}</div>
          </>
        )}
      </section>

      <ConfirmActionModal
        isOpen={isAddOpen}
        title="Добавить пользователя"
        description="Создание пользователя потребует подтверждения согласно политике доступа."
        confirmLabel="Создать"
        onConfirm={() => void handleAddUser()}
        onCancel={() => setIsAddOpen(false)}
        isProcessing={isSubmitting}
        isConfirmDisabled={!newEmail}
        footerNote="Действие будет зафиксировано в audit-логе."
      >
        <label className="filter">
          Email
          <input value={newEmail} onChange={(event) => setNewEmail(event.target.value)} />
        </label>
        <label className="filter">
          Роль
          <select value={newRole} onChange={(event) => setNewRole(event.target.value)}>
            <option value="CLIENT_USER">CLIENT_USER</option>
            <option value="CLIENT_ADMIN">CLIENT_ADMIN</option>
            <option value="CLIENT_OWNER">CLIENT_OWNER</option>
          </select>
        </label>
        {addError ? (
          <div className="notice error">
            {addError.message}
            {addError.correlationId ? <div className="muted small">Correlation ID: {addError.correlationId}</div> : null}
          </div>
        ) : null}
      </ConfirmActionModal>

      <ConfirmActionModal
        isOpen={Boolean(roleUser)}
        title="Изменить роль"
        description={roleUser ? `Пользователь: ${roleUser.email}` : undefined}
        confirmLabel="Сохранить"
        onConfirm={() => void handleRoleSubmit()}
        onCancel={() => setRoleUser(null)}
        isProcessing={isSubmitting}
        isConfirmDisabled={!roleUser}
        footerNote="Действие будет зафиксировано в audit-логе."
      >
        <label className="filter">
          Роль
          <select value={roleValue} onChange={(event) => setRoleValue(event.target.value)}>
            <option value="CLIENT_USER">CLIENT_USER</option>
            <option value="CLIENT_ADMIN">CLIENT_ADMIN</option>
            <option value="CLIENT_OWNER">CLIENT_OWNER</option>
          </select>
        </label>
        {roleError ? (
          <div className="notice error">
            {roleError.message}
            {roleError.correlationId ? <div className="muted small">Correlation ID: {roleError.correlationId}</div> : null}
          </div>
        ) : null}
      </ConfirmActionModal>

      <ConfirmActionModal
        isOpen={Boolean(disableUser)}
        title="Отключить пользователя"
        description={disableUser ? `Пользователь: ${disableUser.email}` : undefined}
        confirmLabel="Отключить"
        onConfirm={() => void handleDisable()}
        onCancel={() => setDisableUser(null)}
        isProcessing={isSubmitting}
        isConfirmDisabled={!disableUser}
        footerNote="Действие будет зафиксировано в audit-логе."
      >
        <div className="muted">Подтвердите отключение доступа пользователя.</div>
        {disableError ? (
          <div className="notice error">
            {disableError.message}
            {disableError.correlationId ? <div className="muted small">Correlation ID: {disableError.correlationId}</div> : null}
          </div>
        ) : null}
      </ConfirmActionModal>
    </div>
  );
}
