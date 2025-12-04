import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { listUsers, updateUser } from "../api/adminUsers";
import { useAuth } from "../auth/AuthContext";
import type { AdminUser, RoleOption } from "../types/users";

const ROLE_OPTIONS: RoleOption[] = ["PLATFORM_ADMIN", "CLIENT_OWNER", "CLIENT_MANAGER", "CLIENT_VIEWER"];

export const EditUserPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { accessToken } = useAuth();
  const navigate = useNavigate();
  const [current, setCurrent] = useState<AdminUser | null>(null);
  const [fullName, setFullName] = useState("");
  const [roles, setRoles] = useState<RoleOption[]>([]);
  const [isActive, setIsActive] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id || !accessToken) return;
    listUsers(accessToken)
      .then((users) => {
        const found = users.find((u) => u.id === id);
        if (found) {
          setCurrent(found);
          setFullName(found.full_name ?? "");
          setRoles(found.roles);
          setIsActive(found.is_active);
        }
      })
      .catch((err) => {
        console.error("Не удалось загрузить пользователя", err);
        setError("Не удалось загрузить пользователя");
      });
  }, [id, accessToken]);

  const toggleRole = (role: RoleOption) => {
    setRoles((curr) => (curr.includes(role) ? curr.filter((r) => r !== role) : [...curr, role]));
  };

  const canSave = useMemo(() => Boolean(current && roles.length > 0), [current, roles]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!accessToken || !current) return;
    setError(null);
    try {
      const updated = await updateUser(accessToken, current.id, {
        full_name: fullName,
        is_active: isActive,
        roles,
      });
      setCurrent(updated);
      navigate("/users");
    } catch (err) {
      console.error("Ошибка обновления", err);
      setError("Не удалось сохранить изменения");
    }
  };

  if (!current) {
    return <div className="card">{error ?? "Загрузка пользователя..."}</div>;
  }

  return (
    <div className="card">
      <h2>Редактирование пользователя</h2>
      <p className="muted">{current.email}</p>
      {error ? <div className="error-text">{error}</div> : null}
      <form className="form-grid" onSubmit={handleSubmit}>
        <label className="label">Полное имя</label>
        <input type="text" value={fullName} onChange={(e) => setFullName(e.target.value)} />

        <label className="label">Активен</label>
        <label className="checkbox">
          <input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} /> Активен
        </label>

        <label className="label">Роли</label>
        <div className="role-grid">
          {ROLE_OPTIONS.map((role) => (
            <label key={role} className="checkbox">
              <input type="checkbox" checked={roles.includes(role)} onChange={() => toggleRole(role)} />
              {role}
            </label>
          ))}
        </div>

        <div style={{ display: "flex", gap: 12 }}>
          <button type="submit" disabled={!canSave}>
            Сохранить
          </button>
          <button type="button" className="ghost" onClick={() => navigate(-1)}>
            Отмена
          </button>
        </div>
      </form>
    </div>
  );
};

export default EditUserPage;
