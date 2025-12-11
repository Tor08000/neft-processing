import { useAuth } from "../auth/AuthContext";

export function ProfilePage() {
  const { user } = useAuth();

  if (!user) {
    return <div className="card">Нет данных о профиле.</div>;
  }

  return (
    <div className="card">
      <h2>Профиль клиента</h2>
      <dl className="meta-grid">
        <div>
          <dt className="label">Email</dt>
          <dd>{user.email}</dd>
        </div>
        <div>
          <dt className="label">ID клиента</dt>
          <dd>{user.clientId ?? "—"}</dd>
        </div>
        <div>
          <dt className="label">Роли</dt>
          <dd>{user.roles.join(", ")}</dd>
        </div>
        <div>
          <dt className="label">Тип субъекта</dt>
          <dd>{user.subjectType}</dd>
        </div>
      </dl>
    </div>
  );
}
