import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { login as loginRequest } from "../api/auth";
import { useAuth } from "../auth/AuthContext";

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { setToken } = useAuth();
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("admin");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const token = await loginRequest(email, password);
      setToken(token);
      navigate("/operations");
    } catch (err: any) {
      setError(err?.message ?? "Не удалось выполнить вход");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <h1>NEFT Admin</h1>
        <p className="muted">Войдите, чтобы посмотреть журнал операций</p>
        <form onSubmit={handleSubmit} className="login-form">
          <label>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label>
            Пароль
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </label>
          {error && <div className="error-text">{error}</div>}
          <button type="submit" disabled={loading}>
            {loading ? "Входим..." : "Войти"}
          </button>
        </form>
      </div>
    </div>
  );
};
