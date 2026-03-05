import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useClient } from "../auth/ClientContext";
import { CopyChip } from "../components/common/CopyChip";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";
import { AppLogo } from "@shared/brand/components";
import { buildSsoStartUrl, listSsoIdps, type SSOIdPItem } from "../api/auth";

export function LoginPage() {
  const { login, error, authError } = useAuth();
  const { portalState, refresh } = useClient();
  const [searchParams] = useSearchParams();
  const [email, setEmail] = useState("client@neft.local");
  const [password, setPassword] = useState("Neft123!");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [signupNotice, setSignupNotice] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [capsLockOn, setCapsLockOn] = useState(false);
  const [tenantId] = useState("00000000-0000-0000-0000-000000000000");
  const [ssoProviders, setSsoProviders] = useState<SSOIdPItem[]>([]);
  const { toast, showToast } = useToast();
  const emailRef = useRef<HTMLInputElement | null>(null);
  const errorRef = useRef<HTMLDivElement | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setFieldError(null);
    try {
      await login({
        email,
        password,
      });
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



  useEffect(() => {
    let cancelled = false;
    listSsoIdps(tenantId)
      .then((response) => {
        if (!cancelled) {
          setSsoProviders(response.idps ?? []);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSsoProviders([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [tenantId]);

  const isFormValid = email.trim().length > 0 && password.length > 0;

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
          <CopyChip label="Demo email" value="client@neft.local" onCopy={() => showToast("success", "Скопировано")} />
          <CopyChip label="Demo password" value="Neft123!" onCopy={() => showToast("success", "Скопировано")} />
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
        {authError === "reauth_required" ? (
          <div className="error" role="alert" tabIndex={-1} ref={errorRef}>
            Требуется повторный вход
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
        <label htmlFor="client-tenant">
          Tenant ID
          <input
            id="client-tenant"
            className="neft-input neft-focus-ring"
            type="text"
            value={tenantId}
            readOnly
            placeholder="00000000-0000-0000-0000-000000000000"
            disabled
          />
        </label>

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
            placeholder="Neft123!"
            required
            autoComplete="current-password"
            disabled={isSubmitting}
            aria-invalid={Boolean(error || fieldError)}
          />
        </label>
        {capsLockOn ? <div className="capslock-hint">Caps Lock включён</div> : null}

        <button type="submit" className="neft-button neft-btn-primary" disabled={isSubmitting || !isFormValid}>
          {isSubmitting ? <span className="neft-spinner" aria-hidden /> : null}
          {isSubmitting ? "Входим..." : "Войти"}
        </button>
        <Link to="/register" className="neft-button neft-btn-secondary neft-btn-outline login-secondary-action">
          {selfSignupLabel}
        </Link>
        <button
          type="button"
          className="neft-button neft-btn-secondary neft-btn-outline login-secondary-action"
          disabled
        >
          Забыли пароль
        </button>
        {ssoProviders.map((idp) => (
          <a
            key={idp.provider_key}
            className="neft-button neft-btn-secondary login-secondary-action"
            href={buildSsoStartUrl(tenantId, idp.provider_key, `${window.location.origin}/login`)}
          >
            {idp.display_name}
          </a>
        ))}
      </form>
      <Toast toast={toast} />
    </div>
  );
}
