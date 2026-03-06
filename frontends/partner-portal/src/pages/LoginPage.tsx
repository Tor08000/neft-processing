import { FormEvent, useMemo, useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { AppLogo } from "@shared/brand/components";
import { CopyChip } from "../components/common/CopyChip";

export function LoginPage() {
  const { login, error, user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnUrl = useMemo(() => searchParams.get("returnUrl") || "/products", [searchParams]);
  const [email, setEmail] = useState("partner@neft.local");
  const [password, setPassword] = useState("Partner123!");
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
      setFieldError("Сервис временно недоступен");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="login-wrapper neft-page">
      <form className="card login-card neft-card" onSubmit={handleSubmit}>
        <div className="login-brand">
          <AppLogo variant="full" size={72} />
        </div>
        <h1>NEFT Platform</h1>
        <p className="muted">Используйте учётные данные партнёра для доступа.</p>
        <div className="login-demo muted small">
          <CopyChip label="Demo" value="partner@neft.local" />
          <CopyChip label="Demo" value="Partner123!" />
        </div>
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
        <label htmlFor="partner-email">
          Email
          <input
            id="partner-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="partner@neft.local"
            required
            autoComplete="username"
            className="neft-input neft-focus-ring"
          />
        </label>

        <label htmlFor="partner-password">
          Пароль
          <input
            id="partner-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Partner123!"
            required
            autoComplete="current-password"
            className="neft-input neft-focus-ring"
          />
        </label>

        <button type="submit" className="neft-button neft-btn-primary" disabled={isSubmitting}>
          {isSubmitting ? "Входим..." : "Войти"}
        </button>
      </form>
    </div>
  );
}
