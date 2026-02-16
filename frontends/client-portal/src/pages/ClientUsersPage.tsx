import { useEffect, useMemo, useState } from "react";
import {
  createClientUser,
  disableClientUser,
  fetchClientInvitations,
  fetchClientUsers,
  resendClientInvitation,
  revokeClientInvitation,
  updateClientUserRole,
} from "../api/controls";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { ConfirmActionModal } from "../components/ConfirmActionModal";
import { AppEmptyState, AppErrorState, AppForbiddenState, AppLoadingState } from "../components/states";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";
import type { ClientInvitationSummary, ClientUserSummary } from "../types/controls";
import { hasAnyRole } from "../utils/roles";

interface PageErrorState {
  message: string;
  status?: number;
  correlationId?: string | null;
}

const roleLabels: Record<string, string> = {
  CLIENT_OWNER: "CLIENT_OWNER",
  CLIENT_MANAGER: "CLIENT_MANAGER",
  CLIENT_VIEWER: "CLIENT_VIEWER",
};

export function ClientUsersPage() {
  const { user } = useAuth();
  const [users, setUsers] = useState<ClientUserSummary[]>([]);
  const [invitations, setInvitations] = useState<ClientInvitationSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<PageErrorState | null>(null);
  const { toast, showToast } = useToast();

  const [isAddOpen, setIsAddOpen] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [newRole, setNewRole] = useState("CLIENT_VIEWER");
  const [addError, setAddError] = useState<PageErrorState | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [roleUser, setRoleUser] = useState<ClientUserSummary | null>(null);
  const [roleValue, setRoleValue] = useState("CLIENT_VIEWER");
  const [roleError, setRoleError] = useState<PageErrorState | null>(null);

  const [disableUser, setDisableUser] = useState<ClientUserSummary | null>(null);
  const [disableError, setDisableError] = useState<PageErrorState | null>(null);
  const [revokeInvite, setRevokeInvite] = useState<ClientInvitationSummary | null>(null);
  const [revokeReason, setRevokeReason] = useState("");
  const [invitationCooldowns, setInvitationCooldowns] = useState<Record<string, number>>({});

  const canManage = hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ADMIN"]);
  const emailValid = newEmail.trim() !== "" && newEmail.includes("@");

  const loadUsers = () => {
    if (!user) return;
    setIsLoading(true);
    setError(null);
    fetchClientUsers(user)
      .then(async (resp) => {
        setUsers(resp.items ?? []);
        const invites = await fetchClientInvitations(user);
        setInvitations(invites.items ?? []);
      })
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
    if (error.status === 403) {
      return <AppForbiddenState message="Недостаточно прав для управления пользователями." />;
    }
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
    setNewRole("CLIENT_VIEWER");
    setAddError(null);
  };

  const handleAddUser = async () => {
    if (!user) return;
    setIsSubmitting(true);
    setAddError(null);
    try {
      const response = await createClientUser(user, { email: newEmail, roles: [newRole] });
      showToast({ kind: "success", text: `Пользователь приглашён: ${newEmail}` });
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
      const response = await updateClientUserRole(user, roleUser.user_id, { roles: [roleValue] });
      showToast({ kind: "success", text: `Роль обновлена: ${roleUser.email ?? roleUser.user_id} → ${roleValue}` });
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



  const handleResendInvite = async (invitation: ClientInvitationSummary) => {
    if (!user) return;
    if (invitationCooldowns[invitation.invitation_id]) return;
    setInvitationCooldowns((state) => ({ ...state, [invitation.invitation_id]: 10 }));
    const timer = setInterval(() => {
      setInvitationCooldowns((state) => {
        const current = state[invitation.invitation_id] ?? 0;
        if (current <= 1) {
          clearInterval(timer);
          const next = { ...state };
          delete next[invitation.invitation_id];
          return next;
        }
        return { ...state, [invitation.invitation_id]: current - 1 };
      });
    }, 1000);

    try {
      await resendClientInvitation(user, invitation.invitation_id, 7);
      showToast({ kind: "success", text: "Приглашение отправлено повторно" });
      loadUsers();
    } catch (err) {
      showToast({ kind: "error", text: "Ошибка отправки приглашения" });
    }
  };

  const handleRevokeInvite = async () => {
    if (!user || !revokeInvite) return;
    setIsSubmitting(true);
    try {
      await revokeClientInvitation(user, revokeInvite.invitation_id, revokeReason || undefined);
      showToast({ kind: "success", text: "Приглашение отозвано" });
      setRevokeInvite(null);
      setRevokeReason("");
      loadUsers();
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDisable = async () => {
    if (!user || !disableUser) return;
    setIsSubmitting(true);
    setDisableError(null);
    try {
      const response = await disableClientUser(user, disableUser.user_id);
      showToast({ kind: "success", text: `Пользователь отключён: ${disableUser.email ?? disableUser.user_id}` });
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
            Пригласить сотрудника
          </button>
        </div>
        {!canManage ? <div className="muted small">Действия доступны только CLIENT_OWNER/CLIENT_MANAGER.</div> : null}
      </section>

      <section className="card">
        {users.length === 0 ? (
          <AppEmptyState title="Пользователей нет" description="Пригласите первого сотрудника." />
        ) : (
          <>
            <table className="table">
              <thead>
                <tr>
                  <th>Имя</th>
                  <th>Email</th>
                  <th>Роли</th>
                  <th>Статус</th>
                  <th>Last login</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {users.map((item) => (
                  <tr key={item.user_id}>
                    <td>{item.full_name ?? "—"}</td>
                    <td>{item.email ?? "—"}</td>
                    <td>{(item.roles ?? []).map((role) => roleLabels[role] ?? role).join(", ") || "—"}</td>
                    <td>{item.status ?? "—"}</td>
                    <td>—</td>
                    <td>
                      <div className="actions">
                        <button
                          type="button"
                          className="secondary"
                          disabled={!canManage || (item.email ?? "").toLowerCase() === (user?.email ?? "").toLowerCase()}
                          onClick={() => {
                            setRoleUser(item);
                            setRoleValue(item.roles?.[0] ?? "CLIENT_VIEWER");
                            setRoleError(null);
                          }}
                        >
                          Изменить роль
                        </button>
                        <button
                          type="button"
                          className="ghost"
                          disabled={!canManage || item.status?.toUpperCase() === "DISABLED" || !item.email}
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


      <section className="card">
        <div className="card__header">
          <div>
            <h3>Приглашения</h3>
            <p className="muted">Управление pending-приглашениями.</p>
          </div>
        </div>
        {invitations.length === 0 ? (
          <AppEmptyState title="Приглашений нет" description="Создайте приглашение для нового пользователя." />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Email</th><th>Роли</th><th>Статус</th><th>Срок</th><th>Отправок</th><th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {invitations.map((item) => (
                <tr key={item.invitation_id}>
                  <td>{item.email}</td>
                  <td>{item.roles.join(", ")}</td>
                  <td>{item.status}</td>
                  <td>{new Date(item.expires_at).toLocaleString()}</td>
                  <td>{item.resent_count}</td>
                  <td>
                    <div className="actions">
                      <button type="button" className="secondary" disabled={item.status !== "PENDING" || !!invitationCooldowns[item.invitation_id]} onClick={() => void handleResendInvite(item)}>
                        {invitationCooldowns[item.invitation_id] ? `Повторить (${invitationCooldowns[item.invitation_id]})` : "Переотправить"}
                      </button>
                      <button type="button" className="ghost" disabled={item.status !== "PENDING"} onClick={() => setRevokeInvite(item)}>
                        Отозвать
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
        isConfirmDisabled={!emailValid}
        footerNote="Действие будет зафиксировано в audit-логе."
      >
        <label className="filter">
          Email
          <input value={newEmail} onChange={(event) => setNewEmail(event.target.value)} />
        </label>
        <label className="filter">
          Роль
          <select value={newRole} onChange={(event) => setNewRole(event.target.value)}>
            <option value="CLIENT_VIEWER">CLIENT_VIEWER</option>
            <option value="CLIENT_MANAGER">CLIENT_MANAGER</option>
            <option value="CLIENT_OWNER">CLIENT_OWNER</option>
          </select>
        </label>
        {addError ? (
          <div className="notice error">
            {addError.message}
            {addError.correlationId ? <div className="muted small">Correlation ID: {addError.correlationId}</div> : null}
          </div>
        ) : null}
        {!emailValid && newEmail ? <div className="muted small">Введите корректный email.</div> : null}
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
            <option value="CLIENT_VIEWER">CLIENT_VIEWER</option>
            <option value="CLIENT_MANAGER">CLIENT_MANAGER</option>
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
      <ConfirmActionModal
        isOpen={Boolean(revokeInvite)}
        title="Отозвать приглашение"
        description={revokeInvite ? `Приглашение: ${revokeInvite.email}` : undefined}
        confirmLabel="Отозвать"
        onConfirm={() => void handleRevokeInvite()}
        onCancel={() => setRevokeInvite(null)}
        isProcessing={isSubmitting}
        isConfirmDisabled={!revokeInvite}
      >
        <label className="filter">
          Причина (опционально)
          <input value={revokeReason} onChange={(event) => setRevokeReason(event.target.value)} />
        </label>
      </ConfirmActionModal>
      {toast ? <Toast toast={toast} onClose={() => showToast(null)} /> : null}
    </div>
  );
}
