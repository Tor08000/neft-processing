import { useAuth } from "../auth/AuthContext";
import { AppForbiddenState } from "../components/states";

export function SettingsPage() {
  const { user } = useAuth();

  if (!user) {
    return <AppForbiddenState message="Требуется авторизация." />;
  }

  return (
    <div className="card">
      <div className="card__header">
        <div>
          <h2>Settings</h2>
          <p className="muted">Read-only параметры доступа и профиля клиента.</p>
        </div>
      </div>
      <dl className="meta-grid">
        <div>
          <dt className="label">Email</dt>
          <dd>{user.email}</dd>
        </div>
        <div>
          <dt className="label">Client ID</dt>
          <dd>{user.clientId ?? "—"}</dd>
        </div>
        <div>
          <dt className="label">Roles</dt>
          <dd>{user.roles.join(", ")}</dd>
        </div>
        <div>
          <dt className="label">Subject type</dt>
          <dd>{user.subjectType}</dd>
        </div>
      </dl>
    </div>
  );
}
