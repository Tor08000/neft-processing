import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { CopyChip } from "../components/common/CopyChip";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";
import { AppLogo } from "@shared/brand/components";

export function LoginPage() {
  const { login, error, user } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnUrl = useMemo(() => searchParams.get("returnUrl") || "/vehicles", [searchParams]);
  const [email, setEmail] = useState("client@neft.local");
  const [password, setPassword] = useState("client");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [capsLockOn, setCapsLockOn] = useState(false);
  const { toast, showToast } = useToast();
  const emailRef = useRef<HTMLInputElement | null>(null);
  const errorRef = useRef<HTMLDivElement | null>(null);

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
      showToast("error", "Сервис временно недоступен");
    } finally {
      setIsSubmitting(false);
    }
  };

  useEffect(() => {
    emailRef.current?.focus();
  }, []);

  useEffect(() => {
    if (error || fieldError) {
      errorRef.current?.focus();
    }
  }, [error, fieldError]);

  return (
    <div className="login-wrapper neft-page">
      <form className="card login-card neft-card" onSubmit={handleSubmit}>
        <div className="login-brand">
          <AppLogo variant="full" size={72} />
        </div>
        <h1>NEFT Platform</h1>
        <p>Используйте демо-учётные данные, чтобы продолжить работу.</p>
        <div className="login-demo">
          <CopyChip label="Demo" value="client@neft.local" onCopy={() => showToast("success", "Скопировано")} />
          <CopyChip label="Demo" value="client" onCopy={() => showToast("success", "Скопировано")} />
        </div>
        {error ? (
          <div className="error" role="alert" tabIndex={-1} ref={errorRef}>
            {error}
          </div>
        ) : null}
        {fieldError ? (
          <div className="error" role="alert" tabIndex={-1} ref={errorRef}>
            {fieldError}
          </div>
        ) : null}
        <label htmlFor="client-email">
          Email
          <input
            ref={emailRef}
            id="client-email"
            className="neft-input neft-focus-ring"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="client@neft.local"
            required
            autoComplete="username"
            disabled={isSubmitting}
            aria-invalid={Boolean(error || fieldError)}
          />
        </label>

        <label htmlFor="client-password">
          Пароль
          <input
            id="client-password"
            className="neft-input neft-focus-ring"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyUp={(event) => setCapsLockOn(event.getModifierState("CapsLock"))}
            onBlur={() => setCapsLockOn(false)}
            placeholder="client"
            required
            autoComplete="current-password"
            disabled={isSubmitting}
            aria-invalid={Boolean(error || fieldError)}
          />
        </label>
        {capsLockOn ? <div className="capslock-hint">Caps Lock включён</div> : null}

        <button type="submit" className="neft-button neft-btn-primary" disabled={isSubmitting}>
          {isSubmitting ? <span className="neft-spinner" aria-hidden /> : null}
          {isSubmitting ? "Входим..." : "Войти"}
        </button>
      </form>
      <Toast toast={toast} />
    </div>
  );
}
