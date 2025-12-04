import React, { useEffect, useState } from "react";
import { listUsers } from "../api/adminUsers";
import { useAuth } from "../auth/AuthContext";
import type { AdminUser } from "../types/users";

export const DashboardPage: React.FC = () => {
  const { user, accessToken, logout } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!accessToken) return;
    listUsers(accessToken)
      .then((data) => setUsers(data))
      .catch((err) => {
        console.error("Не удалось загрузить пользователей", err);
        setError("Не удалось загрузить данные пользователей");
        if (err instanceof Error && err.name === "UnauthorizedError") {
          logout();
        }
      });
  }, [accessToken, logout]);

  return (
    <div className="stack">
      <div className="card">
        <h2>Добро пожаловать, {user?.email}</h2>
        <p className="muted">Роль: {user?.roles.join(", ")}</p>
      </div>

      <div className="card">
        <h3>Пользователи системы</h3>
        {error ? <div className="error-text">{error}</div> : null}
        <p>Загружено: {users.length}</p>
        <div className="pill-list">
          {users.slice(0, 5).map((item) => (
            <span key={item.id} className="pill">
              {item.email}
            </span>
          ))}
        </div>
      </div>

      <div className="card">
        <h3>Мониторинг</h3>
        <p className="muted">Секции для клиентских аккаунтов, операций и мониторинга появятся позже.</p>
      </div>
    </div>
  );
};

export default DashboardPage;
