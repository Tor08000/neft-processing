import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useClient } from "../auth/ClientContext";
import { CopyChip } from "../components/common/CopyChip";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";
import { AppLogo } from "@shared/brand/components";

export function LoginPage() {
  const { login, error, user } = useAuth();
  const { client, portalState, refresh } = useClient();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const returnUrl = useMemo(() => searchParams.get("returnUrl") || "/client/dashboard", [searchParams]);
  const [email, setEmail] = useState("client@neft.local");
  const [password, setPassword] = useState("client");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [signupNotice, setSignupNotice] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [capsLockOn, setCapsLockOn] = useState(false);
  const { toast, showToast } = useToast();
  const emailRef = useRef<HTMLInputElement | null>(null);
  const errorRef = useRef<HTMLDivElement | null>(null);

  const accessState = client?.access_state;
  const redirectTarget = useMemo(() => {
    switch (accessState) {
      case "NEEDS_ONBOARDING":
        return "/client/onboarding";
      case "NEEDS_PLAN":
        return "/client/onboarding/plan";
      case "NEEDS_CONTRACT":
        return "/client/onboarding/contract";
      case "OVERDUE":
        return "/client/billing/overdue";
      case "SERVICE_UNAVAILABLE":
        return "/client/service-unavailable";
      case "TECH_ERROR":
        return "/client/tech-error";
      case "ACTIVE":
        return returnUrl;
      default:
        return returnUrl;
    }
  }, [accessState, returnUrl]);

  useEffect(() => {
    if (!user || portalState !== "READY") return;
    if (redirectTarget) {
      navigate(redirectTarget, { replace: true });
    }
  }, [navigate, portalState, redirectTarget, user]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    setFieldError(null);
    try {
      await login(email, password);
      await refresh();
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
    if (signupNotice) return;
    if (searchParams.get("signup") === "success") {
      setSignupNotice("Аккаунт создан — войдите.");
      showToast("success", "Аккаунт создан — войдите.");
    }
  }, [searchParams, showToast, signupNotice]);

  useEffect(() => {
    if (error || fieldError) {
      errorRef.current?.focus();
    }
  }, [error, fieldError]);

  const portalStateMessage = useMemo(() => {
    switch (portalState) {
      case "LOADING":
        return "Проверяем доступ...";
      case "SERVICE_UNAVAILABLE":
        return "Сервис временно недоступен. Попробуйте позже.";
      case "NETWORK_DOWN":
        return "Нет соединения с сервером. Проверьте подключение к интернету.";
      case "API_MISCONFIGURED":
        return "Маршрут портала недоступен. Проверьте настройки API.";
      case "ERROR_FATAL":
        return "Не удалось загрузить профиль клиента.";
      default:
        return null;
    }
  }, [portalState]);

  const selfSignupLabel = "Регистрация";

  return (
    <div className="login-wrapper neft-page">
      <form className="card login-card neft-card" onSubmit={handleSubmit}>
        <div className="login-brand">
          <AppLogo variant="full" size={72} />
        </div>
        <h1>NEFT Platform</h1>
        <p className="muted">Используйте демо-учётные данные, чтобы продолжить работу.</p>
        <div className="login-demo muted small">
          <CopyChip label="Demo" value="client@neft.local" onCopy={() => showToast("success", "Скопировано")} />
          <CopyChip label="Demo" value="client" onCopy={() => showToast("success", "Скопировано")} />
        </div>
        {portalStateMessage ? (
          <div className="error" role="alert" tabIndex={-1} ref={errorRef}>
            {portalStateMessage}
            {portalState !== "LOADING" ? (
              <button
                type="button"
                className="ghost neft-btn-secondary"
                onClick={refresh}
                disabled={isSubmitting}
              >
                Повторить
              </button>
            ) : null}
          </div>
        ) : null}
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
        {signupNotice ? (
          <div className="success" role="status" tabIndex={-1} ref={errorRef}>
            {signupNotice}
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
            disabled={isSubmitting || Boolean(user)}
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
            disabled={isSubmitting || Boolean(user)}
            aria-invalid={Boolean(error || fieldError)}
          />
        </label>
        {capsLockOn ? <div className="capslock-hint">Caps Lock включён</div> : null}

        <button type="submit" className="neft-button neft-btn-primary" disabled={isSubmitting || Boolean(user)}>
          {isSubmitting ? <span className="neft-spinner" aria-hidden /> : null}
          {isSubmitting ? "Входим..." : "Войти"}
        </button>
        <Link to="/client/signup" className="neft-button neft-btn-secondary neft-btn-outline login-secondary-action">
          {selfSignupLabel}
        </Link>
        <button
          type="button"
          className="neft-button neft-btn-secondary neft-btn-outline login-secondary-action"
          disabled
        >
          Забыли пароль
        </button>
      </form>
      <Toast toast={toast} />
    </div>
  );
}
