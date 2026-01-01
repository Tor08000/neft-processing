import { FormEvent, useMemo, useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function LoginPage() {
  const { login, error, user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnUrl = useMemo(() => searchParams.get("returnUrl") || "/finance/invoices", [searchParams]);
  const [email, setEmail] = useState("client@neft.local");
  const [password, setPassword] = useState("client");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [fieldError, setFieldError] = useState<string | null>(null);

  if (user) {
    return <Navigate to={returnUrl} replace />;
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    setFieldError(null);
    try {
      await login(email, password);
      navigate(returnUrl, { replace: true });
    } catch (err) {
      console.error("Ошибка входа", err);
      setFieldError("Ошибка авторизации, попробуйте позже");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="login-wrapper neft-page">
      <form className="card login-card neft-card" onSubmit={handleSubmit}>
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
            className="neft-input"
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
            className="neft-input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="client"
            required
            autoComplete="current-password"
          />
        </label>

        <button type="submit" className="primary neft-btn-primary" disabled={isSubmitting}>
          {isSubmitting ? "Входим..." : "Войти"}
        </button>
      </form>
    </div>
  );
}
