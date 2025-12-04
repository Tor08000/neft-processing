import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { listUsers, updateUser } from "../api/adminUsers";
import { UnauthorizedError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import type { AdminUser } from "../types/users";

export const UsersPage: React.FC = () => {
  const { user, logout } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    listUsers(user.token)
      .then((data) => setUsers(data))
      .catch((err) => {
        console.error("Ошибка загрузки пользователей", err);
        if (err instanceof UnauthorizedError) {
          logout();
          return;
        }
        setError("Не удалось загрузить пользователей");
      })
      .finally(() => setLoading(false));
  }, [user, logout]);

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return users;
    return users.filter((u) => u.email.toLowerCase().includes(query));
  }, [users, search]);

  const toggleActive = async (item: AdminUser) => {
    if (!user) return;
    try {
      const updated = await updateUser(user.token, item.id, { is_active: !item.is_active });
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
    } catch (err) {
      console.error("Не удалось обновить пользователя", err);
      setError("Не удалось обновить пользователя");
    }
  };

  return (
    <div className="stack">
      <div className="page-header">
        <div>
          <h2>Пользователи</h2>
          <p className="muted">Управление доступом к платформе</p>
        </div>
        <Link to="/users/new" className="button primary">Создать пользователя</Link>
      </div>

      <div className="card" style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <label className="label" htmlFor="email-filter">
          Фильтр по email
        </label>
        <input
          id="email-filter"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="client@neft.local"
          style={{ maxWidth: 260 }}
        />
      </div>

      {error ? <div className="error-text">{error}</div> : null}

      <div className="table-container">
        <table className="table">
          <thead>
            <tr>
              <th>Email</th>
              <th>Полное имя</th>
              <th>Активен</th>
              <th>Роли</th>
              <th>Создан</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6}>Загрузка...</td>
              </tr>
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={6}>Пользователи не найдены</td>
              </tr>
            ) : (
              filtered.map((item) => (
                <tr key={item.id}>
                  <td>{item.email}</td>
                  <td>{item.full_name ?? "—"}</td>
                  <td>
                    <button className="ghost" onClick={() => toggleActive(item)}>
                      {item.is_active ? "Активен" : "Выключен"}
                    </button>
                  </td>
                  <td>{item.roles.join(", ")}</td>
                  <td>{item.created_at ? new Date(item.created_at).toLocaleString() : "—"}</td>
                  <td>
                    <Link to={`/users/${item.id}`}>Редактировать</Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default UsersPage;
