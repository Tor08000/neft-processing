import React, { useEffect, useRef, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { CopyChip } from "../components/common/CopyChip";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";
import { AppLogo } from "@shared/brand/components";

export const LoginPage: React.FC = () => {
  const { login, error, accessToken } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("admin123");
  const [submitting, setSubmitting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [capsLockOn, setCapsLockOn] = useState(false);
  const { toast, showToast } = useToast();
  const emailRef = useRef<HTMLInputElement | null>(null);
  const errorRef = useRef<HTMLDivElement | null>(null);
  const showGatewayHint = typeof window !== "undefined" && window.location.port === "4173";

  if (accessToken) {
    return <Navigate to="/" replace />;
  }

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setLocalError(null);
    try {
      await login(email, password);
    } catch (err) {
      console.error("Ошибка входа", err);
      const message = err instanceof TypeError ? "Сервис временно недоступен" : "Техническая ошибка";
      setLocalError(message);
      showToast("error", message);
    } finally {
      setSubmitting(false);
    }
  };

  useEffect(() => {
    emailRef.current?.focus();
  }, []);

  useEffect(() => {
    if (accessToken) {
      navigate("/", { replace: true });
    }
  }, [accessToken, navigate]);

  useEffect(() => {
    if (error || localError) {
      errorRef.current?.focus();
    }
  }, [error, localError]);

  return (
    <div className="login-page neft-page">
      <div className="login-card neft-card">
        <div className="login-brand">
          <AppLogo variant="full" size={72} />
        </div>
        <h1>NEFT Platform</h1>
        <p className="muted">Войдите под учётными данными администратора платформы.</p>
        {showGatewayHint ? (
          <div className="muted small">
            Откройте админ-портал через{" "}
            <a className="neft-link" href="http://localhost/admin">
              http://localhost/admin
            </a>
            .
          </div>
        ) : null}
        <div className="login-demo muted small">
          <CopyChip label="Demo" value="admin@example.com" onCopy={() => showToast("success", "Скопировано")} />
          <CopyChip label="Demo" value="admin123" onCopy={() => showToast("success", "Скопировано")} />
        </div>
        <form onSubmit={handleSubmit} className="login-form">
          <label htmlFor="admin-email">
            Email
            <input
              ref={emailRef}
              id="admin-email"
              className="neft-input neft-focus-ring"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@example.com"
              required
              autoComplete="username"
              disabled={submitting}
              aria-invalid={Boolean(error || localError)}
            />
          </label>
          <label htmlFor="admin-password">
            Пароль
            <input
              id="admin-password"
              className="neft-input neft-focus-ring"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyUp={(event) => setCapsLockOn(event.getModifierState("CapsLock"))}
              onBlur={() => setCapsLockOn(false)}
              placeholder="admin123"
              required
              autoComplete="current-password"
              disabled={submitting}
              aria-invalid={Boolean(error || localError)}
            />
          </label>
          {capsLockOn ? <div className="capslock-hint">Caps Lock включён</div> : null}
          {(error || localError) && (
            <div className="error-text" role="alert" tabIndex={-1} ref={errorRef}>
              {error ?? localError}
            </div>
          )}
          <button type="submit" className="neft-button neft-btn-primary" disabled={submitting}>
            {submitting ? <span className="neft-spinner" aria-hidden /> : null}
            {submitting ? "Входим..." : "Войти"}
          </button>
        </form>
      </div>
      <Toast toast={toast} />
    </div>
  );
};

export default LoginPage;
