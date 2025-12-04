import { useMemo } from "react";
import { useAuth } from "../auth/AuthContext";

function formatExpiry(timestamp: number | undefined) {
  if (!timestamp) return "—";
  const diffMs = timestamp - Date.now();
  if (diffMs <= 0) return "истек";
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "менее минуты";
  if (minutes < 60) return `${minutes} мин`;
  const hours = Math.floor(minutes / 60);
  const restMinutes = minutes % 60;
  return `${hours} ч ${restMinutes} мин`;
}

export function DashboardPage() {
  const { user } = useAuth();

  const abilities = useMemo(() => {
    if (!user) return [];
    const list = [] as string[];
    if (user.roles.includes("CLIENT_OWNER")) {
      list.push("Вы являетесь владельцем аккаунта клиента");
    }
    user.roles
      .filter((role) => role !== "CLIENT_OWNER")
      .forEach((role) => list.push(`Роль: ${role}`));
    return list;
  }, [user]);

  if (!user) {
    return null;
  }

  return (
    <div className="stack" aria-live="polite">
      <section className="card">
        <h2>Здравствуйте, {user.email}</h2>
        <p className="muted">Добро пожаловать в клиентский кабинет NEFT.</p>
      </section>

      <section className="card">
        <h3>Ваши роли</h3>
        <ul className="pill-list">
          {user.roles.map((role) => (
            <li key={role}>{role}</li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h3>Ваши текущие возможности</h3>
        {abilities.length ? (
          <ul className="bullets">
            {abilities.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <p className="muted">Роли не назначены.</p>
        )}
      </section>

      <section className="card">
        <h3>Статус авторизации</h3>
        <div className="meta-grid">
          <div>
            <div className="label">Email</div>
            <div>{user.email}</div>
          </div>
          <div>
            <div className="label">Тип субъекта</div>
            <div>{user.subjectType}</div>
          </div>
          <div>
            <div className="label">ID клиента</div>
            <div>{user.clientId ?? "—"}</div>
          </div>
          <div>
            <div className="label">Токен истекает через</div>
            <div>{formatExpiry(user.expiresAt)}</div>
          </div>
        </div>
      </section>
    </div>
  );
}
