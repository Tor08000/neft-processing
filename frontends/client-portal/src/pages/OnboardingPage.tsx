import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { EmptyState } from "@shared/brand/components";
import { useAuth } from "../auth/AuthContext";
import { useClient } from "../auth/ClientContext";
import {
  createOrg,
  fetchPlans,
  selectSubscription,
  generateContract,
  fetchCurrentContract,
  signContract,
  type ContractInfo,
  type SubscriptionPlan,
} from "../api/clientPortal";
import { AccessState } from "../access/accessState";
import {
  AUTO_ACTIVATE_AFTER_SIGN,
  CONTRACT_SIMPLE_SIGN_ENABLED,
  INDIVIDUAL_SIGNUP_ENABLED,
  SELF_SIGNUP_ENABLED,
} from "../config/features";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";

type Step = "profile" | "plan" | "contract" | "activation";

export function OnboardingPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { client, refresh } = useClient();
  const { toast, showToast } = useToast();
  const [step, setStep] = useState<Step>("profile");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const onboardingEnabled = client?.gating?.onboarding_enabled ?? client?.features?.onboarding_enabled ?? SELF_SIGNUP_ENABLED;

  const [clientType, setClientType] = useState<"LEGAL" | "IP" | "INDIVIDUAL">("LEGAL");
  const [companyName, setCompanyName] = useState("");
  const [inn, setInn] = useState("");
  const [kpp, setKpp] = useState("");
  const [ogrn, setOgrn] = useState("");
  const [ogrnip, setOgrnip] = useState("");
  const [legalAddress, setLegalAddress] = useState("");
  const [contactName, setContactName] = useState("");
  const [contactRole, setContactRole] = useState("");
  const [contactPhone, setContactPhone] = useState("");
  const [contactEmail, setContactEmail] = useState("");

  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [selectedPlan, setSelectedPlan] = useState<string>("");

  const [contractInfo, setContractInfo] = useState<ContractInfo | null>(null);
  const [contractReady, setContractReady] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [simpleSignConsent, setSimpleSignConsent] = useState(false);
  const [otp, setOtp] = useState("");

  const activationLabel = useMemo(() => {
    if (client?.org_status === "ACTIVE") return "Аккаунт активирован";
    return "Ожидайте активации";
  }, [client?.org_status]);

  useEffect(() => {
    if (!user || !onboardingEnabled) return;
    if (client?.access_state === AccessState.ACTIVE) {
      setStep("activation");
      return;
    }
    if (client?.access_state === AccessState.NEEDS_CONTRACT) {
      setStep("contract");
      return;
    }
    if (client?.access_state === AccessState.NEEDS_PLAN) {
      setStep("plan");
      return;
    }
    setStep("profile");
  }, [client?.access_state, onboardingEnabled, user]);

  useEffect(() => {
    if (step !== "plan" || !user) return;
    if (plans.length) return;
    setIsLoading(true);
    fetchPlans(user)
      .then((data) => {
        setPlans(data);
        const freePlan = data.find((plan) => plan.code.toUpperCase().includes("FREE"));
        if (freePlan) {
          setSelectedPlan(freePlan.code);
        } else if (data[0]) {
          setSelectedPlan(data[0].code);
        }
      })
      .catch((err) => {
        console.error("Не удалось загрузить планы", err);
        setError("Не удалось загрузить планы подписки");
      })
      .finally(() => setIsLoading(false));
  }, [plans.length, step, user]);

  useEffect(() => {
    if (step !== "contract" || !user) return;
    if (contractReady) return;
    fetchCurrentContract(user)
      .then((data) => {
        setContractInfo(data);
        setContractReady(true);
      })
      .catch(() => {
        setContractReady(false);
      });
  }, [contractReady, step, user]);

  if (!onboardingEnabled) {
    return (
      <EmptyState
        title="Онбординг отключён"
        description="Онбординг клиента отключён администратором."
        action={
          <button type="button" className="ghost neft-btn-secondary" onClick={() => navigate("/dashboard")}>
            Перейти в кабинет
          </button>
        }
      />
    );
  }

  const handleProfileSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!user) return;
    if (!companyName || !inn || !legalAddress || !contactName || !contactPhone || !contactEmail) {
      setError("Заполните обязательные поля");
      return;
    }
    if (clientType === "LEGAL" && !kpp) {
      setError("КПП обязателен для юридических лиц");
      return;
    }
    if (clientType === "LEGAL" && !ogrn) {
      setError("ОГРН обязателен для юридических лиц");
      return;
    }
    if (clientType === "IP" && !ogrnip) {
      setError("ОГРНИП обязателен для ИП");
      return;
    }
    setIsLoading(true);
    try {
      await createOrg(user, {
        org_type: clientType,
        name: companyName,
        inn,
        kpp: clientType === "LEGAL" ? kpp : null,
        ogrn: clientType === "LEGAL" ? ogrn : null,
        address: legalAddress,
      });
      await refresh();
      setStep("plan");
      showToast("success", "Профиль сохранён");
    } catch (err) {
      console.error("Ошибка сохранения профиля", err);
      setError("Не удалось сохранить профиль");
      showToast("error", "Не удалось сохранить профиль");
    } finally {
      setIsLoading(false);
    }
  };

  const handlePlanSelect = async () => {
    if (!user) return;
    if (!selectedPlan) {
      setError("Выберите план подписки");
      return;
    }
    setIsLoading(true);
    try {
      await selectSubscription(user, { plan_code: selectedPlan });
      await refresh();
      setStep("contract");
      showToast("success", "Подписка выбрана");
    } catch (err) {
      console.error("Ошибка выбора подписки", err);
      setError("Не удалось выбрать подписку");
      showToast("error", "Не удалось выбрать подписку");
    } finally {
      setIsLoading(false);
    }
  };

  const handleContractGenerate = async () => {
    if (!user) return;
    setIsLoading(true);
    try {
      const response = await generateContract(user);
      setContractInfo(response);
      setContractReady(true);
      showToast("success", "Договор сформирован");
    } catch (err) {
      console.error("Ошибка генерации договора", err);
      showToast("error", "Не удалось сформировать договор");
    } finally {
      setIsLoading(false);
    }
  };

  const handleContractSign = async () => {
    if (!user) return;
    if (!acknowledged || !accepted || !simpleSignConsent) {
      setError("Подтвердите все условия перед подписанием");
      return;
    }
    if (!otp.trim()) {
      setError("Введите код подтверждения");
      return;
    }
    setIsLoading(true);
    setError(null);
    if (!contractInfo?.contract_id) {
      setError("Сначала сформируйте договор");
      return;
    }
    try {
      const response = await signContract(user, contractInfo.contract_id, { otp: otp.trim() });
      setContractInfo(response);
      await refresh();
      setStep("activation");
      showToast("success", "Договор подписан");
    } catch (err) {
      console.error("Ошибка подписи договора", err);
      setError("Не удалось подписать договор");
      showToast("error", "Не удалось подписать договор");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="neft-page onboarding-page">
      <div className="card neft-card onboarding-card">
        <h1>Онбординг клиента</h1>
        <p className="muted">Шаг {step === "profile" ? 1 : step === "plan" ? 2 : step === "contract" ? 3 : 4} из 4</p>
        {error ? <div className="error">{error}</div> : null}
        {isLoading ? <div className="muted">Загружаем данные...</div> : null}
        {step === "profile" ? (
          <form className="onboarding-form" onSubmit={handleProfileSubmit}>
            <label htmlFor="client-type">
              Тип клиента
              <select
                id="client-type"
                className="neft-select neft-input"
                value={clientType}
                onChange={(e) => setClientType(e.target.value as "LEGAL" | "IP" | "INDIVIDUAL")}
              >
                <option value="LEGAL">Юридическое лицо</option>
                <option value="IP">ИП</option>
                {INDIVIDUAL_SIGNUP_ENABLED ? <option value="INDIVIDUAL">Физлицо</option> : null}
              </select>
            </label>
            <label>
              Полное наименование
              <input className="neft-input" value={companyName} onChange={(e) => setCompanyName(e.target.value)} />
            </label>
            <label>
              ИНН
              <input className="neft-input" value={inn} onChange={(e) => setInn(e.target.value)} />
            </label>
            {clientType === "LEGAL" ? (
              <label>
                КПП
                <input className="neft-input" value={kpp} onChange={(e) => setKpp(e.target.value)} />
              </label>
            ) : null}
            {clientType === "LEGAL" ? (
              <label>
                ОГРН
                <input className="neft-input" value={ogrn} onChange={(e) => setOgrn(e.target.value)} />
              </label>
            ) : null}
            {clientType === "IP" ? (
              <label>
                ОГРНИП
                <input className="neft-input" value={ogrnip} onChange={(e) => setOgrnip(e.target.value)} />
              </label>
            ) : null}
            <label>
              Юридический адрес
              <input className="neft-input" value={legalAddress} onChange={(e) => setLegalAddress(e.target.value)} />
            </label>
            <div className="onboarding-section">
              <h3>Контактное лицо</h3>
              <label>
                ФИО
                <input className="neft-input" value={contactName} onChange={(e) => setContactName(e.target.value)} />
              </label>
              <label>
                Должность
                <input className="neft-input" value={contactRole} onChange={(e) => setContactRole(e.target.value)} />
              </label>
              <label>
                Телефон
                <input className="neft-input" value={contactPhone} onChange={(e) => setContactPhone(e.target.value)} />
              </label>
              <label>
                Email
                <input className="neft-input" value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} />
              </label>
            </div>
            <button type="submit" className="neft-button neft-btn-primary" disabled={isLoading}>
              Продолжить
            </button>
          </form>
        ) : null}
        {step === "plan" ? (
          <div className="onboarding-form">
            <p className="muted">Выберите план и модули для вашей компании.</p>
            <label>
              План подписки
              <select
                className="neft-select neft-input"
                value={selectedPlan}
                onChange={(event) => setSelectedPlan(event.target.value)}
              >
                <option value="" disabled>
                  Выберите план
                </option>
                {plans.map((plan) => (
                  <option key={plan.code} value={plan.code}>
                    {plan.title ?? plan.code}
                  </option>
                ))}
              </select>
            </label>
            <button type="button" className="neft-button neft-btn-primary" onClick={handlePlanSelect} disabled={isLoading}>
              Продолжить
            </button>
          </div>
        ) : null}
        {step === "contract" ? (
          <div className="onboarding-form">
            <p className="muted">
              Ознакомьтесь с договором и подтвердите согласие на простую электронную подпись.
            </p>
            {contractInfo?.summary ? <div className="contract-summary">{contractInfo.summary}</div> : null}
            {contractInfo?.pdf_url ? (
              <a className="neft-link" href={contractInfo.pdf_url} target="_blank" rel="noreferrer">
                Открыть PDF договора
              </a>
            ) : (
              <p className="muted">PDF договора будет доступен после генерации.</p>
            )}
            <button type="button" className="neft-button neft-btn-secondary" onClick={handleContractGenerate} disabled={isLoading}>
              Сформировать договор
            </button>
            <label className="checkbox-row">
              <input type="checkbox" checked={acknowledged} onChange={(e) => setAcknowledged(e.target.checked)} />
              <span>Ознакомился с договором</span>
            </label>
            <label className="checkbox-row">
              <input type="checkbox" checked={accepted} onChange={(e) => setAccepted(e.target.checked)} />
              <span>Принимаю условия</span>
            </label>
            <label className="checkbox-row">
              <input type="checkbox" checked={simpleSignConsent} onChange={(e) => setSimpleSignConsent(e.target.checked)} />
              <span>Согласен на простую электронную подпись</span>
            </label>
            {!CONTRACT_SIMPLE_SIGN_ENABLED ? (
              <div className="error">Подписание договора временно недоступно</div>
            ) : null}
            <label>
              OTP-код
              <input className="neft-input" value={otp} onChange={(e) => setOtp(e.target.value)} />
            </label>
            <button
              type="button"
              className="neft-button neft-btn-primary"
              onClick={handleContractSign}
              disabled={!CONTRACT_SIMPLE_SIGN_ENABLED || isLoading}
            >
              Подписать договор
            </button>
          </div>
        ) : null}
        {step === "activation" ? (
          <div className="onboarding-form">
            <h2>{activationLabel}</h2>
            <div className="onboarding-status">
              <div>
                <div className="label">Статус заявки</div>
                <div>{client?.org_status ?? "—"}</div>
              </div>
              <div>
                <div className="label">Статус договора</div>
                <div>{contractInfo?.status ?? "SIGNED_SIMPLE"}</div>
              </div>
              <div>
                <div className="label">Автоактивация</div>
                <div>{AUTO_ACTIVATE_AFTER_SIGN ? "Включена" : "Отключена"}</div>
              </div>
            </div>
            <button type="button" className="neft-button neft-btn-primary" onClick={() => navigate("/dashboard")}>
              Перейти в кабинет
            </button>
          </div>
        ) : null}
      </div>
      <Toast toast={toast} />
    </div>
  );
}
