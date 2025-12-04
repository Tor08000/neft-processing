import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { createUser } from "../api/adminUsers";
import { ValidationError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import type { RoleOption } from "../types/users";

const ROLE_OPTIONS: RoleOption[] = ["PLATFORM_ADMIN", "CLIENT_OWNER", "CLIENT_MANAGER", "CLIENT_VIEWER"];

export const CreateUserPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [roles, setRoles] = useState<RoleOption[]>(["CLIENT_VIEWER"]);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const toggleRole = (role: RoleOption) => {
    setRoles((current) =>
      current.includes(role) ? current.filter((r) => r !== role) : [...current, role],
    );
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    if (password !== confirmPassword) {
      setError("Пароль и подтверждение не совпадают");
      return;
    }
    if (!user) return;
    setSubmitting(true);
    try {
      await createUser(user.token, {
        email,
        password,
        full_name: fullName || undefined,
        roles,
      });
      navigate("/users");
    } catch (err) {
      if (err instanceof ValidationError) {
        setError("Проверьте корректность введённых данных");
        return;
      }
      setError("Не удалось создать пользователя");
      console.error("Ошибка создания пользователя", err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="card">
      <h2>Создать пользователя</h2>
      {error ? <div className="error-text">{error}</div> : null}
      <form className="form-grid" onSubmit={handleSubmit}>
        <label className="label">Email</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          placeholder="user@example.com"
        />

        <label className="label">Полное имя</label>
        <input type="text" value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Имя пользователя" />

        <label className="label">Пароль</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />

        <label className="label">Подтверждение пароля</label>
        <input type="password" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required />

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
          <button type="submit" disabled={submitting}>
            {submitting ? "Создаём..." : "Создать"}
          </button>
          <button type="button" className="ghost" onClick={() => navigate(-1)}>
            Отмена
          </button>
        </div>
      </form>
    </div>
  );
};

export default CreateUserPage;
