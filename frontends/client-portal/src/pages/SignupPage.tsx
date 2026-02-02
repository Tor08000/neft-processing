import { FormEvent, useMemo, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { register } from "../api/auth";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import type { AuthSession } from "../api/types";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";

const PHONE_REGEX = /^[+()\d\s-]{6,}$/;

function resolveContactPayload(value: string): { email?: string; phone?: string } | null {
  if (!value.trim()) return null;
  if (value.includes("@")) {
    return { email: value.trim() };
  }
  if (PHONE_REGEX.test(value)) {
    return { phone: value.trim() };
  }
  return null;
}

export function SignupPage() {
  const navigate = useNavigate();
  const { user, activateSession } = useAuth();
  const { toast, showToast } = useToast();
  const [contact, setContact] = useState("");
  const [password, setPassword] = useState("");
  const [consentPersonal, setConsentPersonal] = useState(false);
  const [consentOffer, setConsentOffer] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorKind, setErrorKind] = useState<"SERVICE_UNAVAILABLE" | "TECH_ERROR" | null>(null);

  const contactPayload = useMemo(() => resolveContactPayload(contact), [contact]);

  if (user) {
    return <Navigate to="/onboarding" replace />;
  }

  const submitRegistration = async () => {
    if (!contactPayload) {
      setError("Введите корректный email или телефон");
      return;
    }
    if (!contactPayload.email) {
      setError("Регистрация по телефону пока недоступна");
      return;
    }
    if (!consentPersonal || !consentOffer) {
      setError("Подтвердите согласия");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    setErrorKind(null);
    try {
      const registerResponse = await register({
        email: contactPayload.email,
        password,
        consent_personal_data: consentPersonal,
        consent_offer: consentOffer,
      });
      if (registerResponse.access_token) {
        const session: AuthSession = {
          token: registerResponse.access_token,
          email: registerResponse.email ?? contactPayload.email,
          roles: registerResponse.roles ?? [],
          subjectType: registerResponse.subject_type ?? "client_user",
          clientId: registerResponse.client_id ?? undefined,
          expiresAt: Date.now() + (registerResponse.expires_in ?? 3600) * 1000,
        };
        await activateSession(session);
        navigate("/client/onboarding", { replace: true });
      } else {
        showToast("success", "Аккаунт создан — войдите.");
        navigate("/client/login?signup=success", { replace: true });
      }
    } catch (err) {
      console.error("Ошибка регистрации", err);
      if (err instanceof ApiError) {
        if (err.status === 502 || err.status === 503) {
          setErrorKind("SERVICE_UNAVAILABLE");
          setError("SERVICE_UNAVAILABLE: сервис временно недоступен");
        } else {
          setErrorKind("TECH_ERROR");
          setError("TECH_ERROR: произошла ошибка регистрации");
        }
        showToast("error", "Сервис временно недоступен");
      } else if (err instanceof Error) {
        setError("Не удалось зарегистрироваться");
        showToast("error", "Не удалось зарегистрироваться");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRegister = async (event: FormEvent) => {
    event.preventDefault();
    await submitRegistration();
  };

  return (
    <div className="login-wrapper neft-page">
      <form className="card login-card neft-card" onSubmit={handleRegister}>
        <h1>Регистрация клиента</h1>
        {error ? (
          <div className="error" role="alert">
            <div>{error}</div>
            {errorKind ? (
              <button
                type="button"
                className="ghost neft-btn-secondary"
                onClick={() => submitRegistration()}
                disabled={isSubmitting}
              >
                Повторить
              </button>
            ) : null}
          </div>
        ) : null}
        <>
          <label htmlFor="signup-contact">
            Email
            <input
              id="signup-contact"
              className="neft-input neft-focus-ring"
              value={contact}
              onChange={(e) => setContact(e.target.value)}
              placeholder="client@neft.local"
              required
              disabled={isSubmitting}
            />
          </label>
          <label htmlFor="signup-password">
            Пароль
            <input
              id="signup-password"
              type="password"
              className="neft-input neft-focus-ring"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={isSubmitting}
            />
          </label>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={consentPersonal}
              onChange={(e) => setConsentPersonal(e.target.checked)}
              disabled={isSubmitting}
            />
            <span>Согласен на обработку персональных данных</span>
          </label>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={consentOffer}
              onChange={(e) => setConsentOffer(e.target.checked)}
              disabled={isSubmitting}
            />
            <span>Принимаю оферту регистрации</span>
          </label>
          <button type="submit" className="neft-button neft-btn-primary" disabled={isSubmitting}>
            {isSubmitting ? "Регистрируем..." : "Зарегистрироваться"}
          </button>
        </>
        <button
          type="button"
          className="ghost neft-btn-secondary"
          onClick={() => navigate("/client/login")}
          disabled={isSubmitting}
        >
          Вернуться к входу
        </button>
      </form>
      <Toast toast={toast} />
    </div>
  );
}
