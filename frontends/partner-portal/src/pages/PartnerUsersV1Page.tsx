import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  addPartnerUserV1,
  fetchPartnerUsersV1,
  removePartnerUserV1,
  type PartnerUserRoleV1,
} from "../api/partner";
import { useAuth } from "../auth/AuthContext";
import { usePortal } from "../auth/PortalContext";
import { canManagePartnerUsers } from "../access/partnerWorkspace";
import { ErrorState, LoadingState } from "../components/states";
import { PartnerSupportActions } from "../components/PartnerSupportActions";

const ROLE_OPTIONS = [
  { value: "PARTNER_MANAGER", label: "Manager" },
  { value: "PARTNER_OPERATOR", label: "Operator" },
  { value: "PARTNER_ACCOUNTANT", label: "Finance manager" },
  { value: "PARTNER_ANALYST", label: "Analyst" },
];

const ROLE_LABELS = Object.fromEntries(ROLE_OPTIONS.map((option) => [option.value, option.label])) as Record<string, string>;

const formatDateTime = (value?: string | null) => {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("ru-RU");
  } catch {
    return value;
  }
};

export function PartnerUsersV1Page() {
  const { user } = useAuth();
  const { portal } = usePortal();
  const canManage = canManagePartnerUsers(portal, user?.roles);
  const [users, setUsers] = useState<PartnerUserRoleV1[]>([]);
  const [identifier, setIdentifier] = useState("");
  const [selectedRole, setSelectedRole] = useState("PARTNER_MANAGER");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const load = async () => {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      setUsers(await fetchPartnerUsersV1(user.token));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось загрузить пользователей.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [user]);

  if (!user) return null;
  if (loading) return <LoadingState label="Загружаем пользователей партнёра..." />;
  if (error) return <ErrorState description={error} />;

  const handleAdd = async () => {
    if (!identifier.trim()) return;
    setSubmitting(true);
    setActionError(null);
    try {
      await addPartnerUserV1(
        user.token,
        identifier.includes("@")
          ? { email: identifier.trim(), roles: [selectedRole] }
          : { user_id: identifier.trim(), roles: [selectedRole] },
      );
      setIdentifier("");
      await load();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Не удалось добавить пользователя.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRemove = async (userId: string) => {
    setActionError(null);
    try {
      await removePartnerUserV1(user.token, userId);
      await load();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Не удалось удалить пользователя.");
    }
  };

  return (
    <div className="stack">
      <section className="card">
        <div className="card__header">
          <div>
            <h2>Пользователи партнёра</h2>
            <p className="muted">Команда и роли внутри партнёрской организации. Управление доступно только owner.</p>
          </div>
          <div className="actions">
            <Link className="ghost" to="/partner/profile">
              Профиль
            </Link>
            <Link className="ghost" to="/partner/terms">
              Условия
            </Link>
          </div>
        </div>
        {canManage ? (
          <div className="card__section">
            <div className="grid three">
              <label className="filter">
                Email или user id
                <input
                  value={identifier}
                  onChange={(event) => setIdentifier(event.target.value)}
                  placeholder="manager@partner.ru"
                />
              </label>
              <label className="filter">
                Роль
                <select value={selectedRole} onChange={(event) => setSelectedRole(event.target.value)}>
                  {ROLE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <div className="actions" style={{ alignItems: "end" }}>
                <button type="button" className="primary" onClick={() => void handleAdd()} disabled={submitting || !identifier.trim()}>
                  {submitting ? "Добавляем..." : "Добавить пользователя"}
                </button>
              </div>
            </div>
            {actionError ? <div className="notice error">{actionError}</div> : null}
          </div>
        ) : (
          <div className="notice">Режим только для чтения. Управлять пользователями может только owner партнёра.</div>
        )}

        {users.length === 0 ? (
          <div className="card__section">
            <p className="muted">Пока привязан только базовый владелец или список ещё не заполнен.</p>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Пользователь</th>
                <th>Роли</th>
                <th>Добавлен</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {users.map((item) => (
                <tr key={item.user_id}>
                  <td className="mono">{item.user_id}</td>
                  <td>{item.roles.map((role) => ROLE_LABELS[role] ?? role).join(", ")}</td>
                  <td>{formatDateTime(item.created_at)}</td>
                  <td>
                    {canManage ? (
                      <button type="button" className="ghost" onClick={() => void handleRemove(item.user_id)}>
                        Удалить
                      </button>
                    ) : (
                      <span className="muted">Просмотр</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <PartnerSupportActions
        title="Нужна помощь с командой или доступами?"
        description="Создайте обращение, если роль назначена неверно, пользователь не видит нужный раздел или нужна ручная проверка связи с организацией."
        requestTitle="Нужна помощь с пользователями партнёра"
        relatedLinks={[
          { to: "/support/requests", label: "История обращений" },
          { to: "/partner/profile", label: "Реквизиты" },
        ]}
      />
    </div>
  );
}
