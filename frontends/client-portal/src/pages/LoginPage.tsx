import { FormEvent, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function LoginPage() {
  const { login, error, user } = useAuth();
  const [email, setEmail] = useState("client@neft.local");
  const [password, setPassword] = useState("client");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [fieldError, setFieldError] = useState<string | null>(null);

  if (user) {
    return <Navigate to="/dashboard" replace />;
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    setFieldError(null);
    try {
      await login(email, password);
    } catch (err) {
      console.error("Ошибка входа", err);
      setFieldError("Ошибка авторизации, попробуйте позже");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="login-wrapper">
      <form className="card login-card" onSubmit={handleSubmit}>
        <h1>Вход в клиентский кабинет</h1>
        <p>Используйте демо-учётные данные, чтобы продолжить работу.</p>
        {error ? (
          <div className="error" role="alert">
            {error}
          </div>
        ) : null}
        {fieldError ? (
          <div className="error" role="alert">
            {fieldError}
          </div>
        ) : null}
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="client@neft.local"
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
            placeholder="client"
            required
            autoComplete="current-password"
          />
        </label>

        <button type="submit" className="primary" disabled={isSubmitting}>
          {isSubmitting ? "Входим..." : "Войти"}
        </button>
      </form>
    </div>
  );
}
