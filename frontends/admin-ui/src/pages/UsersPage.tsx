import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { listUsers, updateUser } from "../api/adminUsers";
import { UnauthorizedError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { DataTable } from "../components/common/DataTable";
import type { AdminUser } from "../types/users";

export const UsersPage: React.FC = () => {
  const { accessToken, logout } = useAuth();
  const navigate = useNavigate();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadUsers = useCallback(() => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    listUsers(accessToken)
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
  }, [accessToken, logout]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return users;
    return users.filter((u) => u.email.toLowerCase().includes(query));
  }, [users, search]);

  const filtersActive = search.trim().length > 0;

  const toggleActive = async (item: AdminUser) => {
    if (!accessToken) return;
    try {
      const updated = await updateUser(accessToken, item.id, { is_active: !item.is_active });
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
        <Link to="/users/new" className="button primary neft-btn-primary">
          Создать пользователя
        </Link>
      </div>

      <div className="card" style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <div>
          <label className="label" htmlFor="email-filter">
            Фильтр по email
          </label>
          <input
            id="email-filter"
            className="neft-input neft-focus-ring"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="client@neft.local"
            style={{ maxWidth: 260 }}
          />
        </div>
        <button
          type="button"
          className="button neft-btn-secondary"
          onClick={() => setSearch("")}
          disabled={!filtersActive}
        >
          Сбросить
        </button>
      </div>

      <DataTable
        data={filtered}
        columns={[
          { key: "email", title: "Email", render: (item) => item.email },
          { key: "full_name", title: "Полное имя", render: (item) => item.full_name ?? "—" },
          {
            key: "active",
            title: "Активен",
            render: (item) => (
              <button className="ghost neft-focus-ring" onClick={() => toggleActive(item)}>
                {item.is_active ? "Активен" : "Выключен"}
              </button>
            ),
          },
          { key: "roles", title: "Роли", render: (item) => item.roles.join(", ") },
          {
            key: "created_at",
            title: "Создан",
            render: (item) => (item.created_at ? new Date(item.created_at).toLocaleString() : "—"),
          },
          {
            key: "actions",
            title: "Действия",
            render: (item) => <Link to={`/users/${item.id}`}>Редактировать</Link>,
          },
        ]}
        loading={loading}
        errorState={
          error
            ? {
                title: "Не удалось загрузить пользователей",
                description: error,
                actionLabel: "Повторить",
                actionOnClick: loadUsers,
              }
            : undefined
        }
        emptyState={{
          title: filtersActive ? "Пользователи не найдены" : "Пользователи отсутствуют",
          description: filtersActive ? "Попробуйте изменить фильтры поиска." : "Создайте первого пользователя.",
          actionLabel: filtersActive ? "Сбросить фильтры" : "Создать пользователя",
          actionOnClick: filtersActive ? () => setSearch("") : () => navigate("/users/new"),
        }}
      />
    </div>
  );
};

export default UsersPage;
