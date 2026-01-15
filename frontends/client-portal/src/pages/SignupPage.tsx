import { FormEvent, useMemo, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { register, verifyRegistration, type RegisterResponse } from "../api/auth";
import { useAuth } from "../auth/AuthContext";
import { SELF_SIGNUP_ENABLED } from "../config/features";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";
import { EmptyState } from "@shared/brand/components";

type Step = "register" | "verify";

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
  const [step, setStep] = useState<Step>("register");
  const [contact, setContact] = useState("");
  const [password, setPassword] = useState("");
  const [consentPersonal, setConsentPersonal] = useState(false);
  const [consentOffer, setConsentOffer] = useState(false);
  const [otp, setOtp] = useState("");
  const [registerInfo, setRegisterInfo] = useState<RegisterResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const contactPayload = useMemo(() => resolveContactPayload(contact), [contact]);

  if (user) {
    return <Navigate to="/client/onboarding" replace />;
  }

  if (!SELF_SIGNUP_ENABLED) {
    return (
      <EmptyState
        title="Модуль недоступен"
        description="Самостоятельная регистрация временно отключена."
        action={
          <button type="button" className="ghost neft-btn-secondary" onClick={() => navigate("/login")}>
            Вернуться к входу
          </button>
        }
      />
    );
  }

  const handleRegister = async (event: FormEvent) => {
    event.preventDefault();
    if (!contactPayload) {
      setError("Введите корректный email или телефон");
      return;
    }
    if (!consentPersonal || !consentOffer) {
      setError("Подтвердите согласия");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      const response = await register({
        ...contactPayload,
        password,
        consent_personal_data: consentPersonal,
        consent_offer: consentOffer,
      });
      setRegisterInfo(response);
      setStep("verify");
      showToast("success", "Код отправлен");
    } catch (err) {
      console.error("Ошибка регистрации", err);
      setError("Не удалось зарегистрироваться");
      showToast("error", "Не удалось зарегистрироваться");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleVerify = async (event: FormEvent) => {
    event.preventDefault();
    if (!registerInfo) return;
    if (!otp.trim()) {
      setError("Введите код подтверждения");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    try {
      const session = await verifyRegistration({ verification_id: registerInfo.verification_id, otp: otp.trim() });
      await activateSession(session);
      navigate("/client/onboarding", { replace: true });
    } catch (err) {
      console.error("Ошибка подтверждения", err);
      setError("Неверный код или истёк срок действия");
      showToast("error", "Не удалось подтвердить код");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="login-wrapper neft-page">
      <form className="card login-card neft-card" onSubmit={step === "register" ? handleRegister : handleVerify}>
        <h1>Регистрация клиента</h1>
        {error ? <div className="error">{error}</div> : null}
        {step === "register" ? (
          <>
            <label htmlFor="signup-contact">
              Email или телефон
              <input
                id="signup-contact"
                className="neft-input neft-focus-ring"
                value={contact}
                onChange={(e) => setContact(e.target.value)}
                placeholder="client@neft.local или +7 900 000-00-00"
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
        ) : (
          <>
            <p className="muted">
              Введите код подтверждения, отправленный на {registerInfo?.channel === "sms" ? "телефон" : "email"}.
            </p>
            <label htmlFor="signup-otp">
              Код подтверждения
              <input
                id="signup-otp"
                className="neft-input neft-focus-ring"
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
                placeholder="000000"
                required
                disabled={isSubmitting}
              />
            </label>
            <button type="submit" className="neft-button neft-btn-primary" disabled={isSubmitting}>
              {isSubmitting ? "Проверяем..." : "Подтвердить"}
            </button>
          </>
        )}
        <button type="button" className="ghost neft-btn-secondary" onClick={() => navigate("/login")} disabled={isSubmitting}>
          Вернуться к входу
        </button>
      </form>
      <Toast toast={toast} />
    </div>
  );
}
