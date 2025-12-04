import React, { useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export const LoginPage: React.FC = () => {
  const { login, error, user } = useAuth();
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("admin");
  const [submitting, setSubmitting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  if (user) {
    return <Navigate to="/dashboard" replace />;
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setLocalError(null);
    try {
      await login(email, password);
    } catch (err) {
      console.error("Ошибка входа", err);
      setLocalError("Не удалось выполнить вход, попробуйте позже");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>Админка NEFT</h1>
        <p className="muted">Войдите под учётными данными администратора платформы.</p>
        <p className="muted small">Демонстрационный доступ: admin@example.com / admin</p>
        <form onSubmit={handleSubmit} className="login-form">
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@example.com"
              required
              autoComplete="username"
            />
          </label>
          <label>
            Пароль
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="admin"
              required
              autoComplete="current-password"
            />
          </label>
          {(error || localError) && <div className="error-text">{error ?? localError}</div>}
          <button type="submit" disabled={submitting}>
            {submitting ? "Входим..." : "Войти"}
          </button>
        </form>
      </div>
    </div>
  );
};

export default LoginPage;
