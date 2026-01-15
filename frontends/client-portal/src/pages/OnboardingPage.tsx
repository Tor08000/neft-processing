import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { EmptyState } from "@shared/brand/components";
import { useAuth } from "../auth/AuthContext";
import {
  fetchOnboardingStatus,
  submitOnboardingProfile,
  uploadOnboardingFile,
  generateContract,
  fetchContract,
  signContract,
  type ClientType,
  type OnboardingContractInfo,
  type OnboardingStatusResponse,
} from "../api/onboarding";
import { ApiError, UnauthorizedError } from "../api/http";
import {
  AUTO_ACTIVATE_AFTER_SIGN,
  CONTRACT_SIMPLE_SIGN_ENABLED,
  INDIVIDUAL_SIGNUP_ENABLED,
  ONBOARDING_DOCS_REQUIRED,
  SELF_SIGNUP_ENABLED,
} from "../config/features";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";

type Step = "profile" | "docs" | "contract" | "activation";

const FILE_TYPES = [
  { value: "company_card", label: "Карточка предприятия / реквизиты" },
  { value: "charter", label: "Устав" },
  { value: "power_of_attorney", label: "Доверенность" },
];

const resolveStepFromStatus = (status: OnboardingStatusResponse | null): Step => {
  if (!status) return "profile";
  if (status.status === "ACTIVE" || status.status === "PENDING_ACTIVATION" || status.status === "CONTRACT_SIGNED") {
    return "activation";
  }
  if (status.status === "CONTRACT_READY") return "contract";
  if (status.status === "ONBOARDING_DOCS") return ONBOARDING_DOCS_REQUIRED ? "docs" : "contract";
  return "profile";
};

export function OnboardingPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { toast, showToast } = useToast();
  const [status, setStatus] = useState<OnboardingStatusResponse | null>(null);
  const [step, setStep] = useState<Step>("profile");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [clientType, setClientType] = useState<ClientType>("LEGAL_ENTITY");
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

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedFileType, setSelectedFileType] = useState(FILE_TYPES[0].value);
  const [uploadedFiles, setUploadedFiles] = useState<Array<{ name: string; type: string; status: string }>>([]);

  const [contractInfo, setContractInfo] = useState<OnboardingContractInfo | null>(null);
  const [contractReady, setContractReady] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [simpleSignConsent, setSimpleSignConsent] = useState(false);
  const [otp, setOtp] = useState("");

  const activationLabel = useMemo(() => {
    if (status?.status === "ACTIVE") return "Аккаунт активирован";
    return "Ожидайте активации";
  }, [status?.status]);

  useEffect(() => {
    if (!user || !SELF_SIGNUP_ENABLED) return;
    let isMounted = true;
    const loadStatus = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const data = await fetchOnboardingStatus(user);
        if (!isMounted) return;
        if (!data) {
          setStatus(null);
          setStep("profile");
          return;
        }
        setStatus(data);
        setStep(resolveStepFromStatus(data));
      } catch (err) {
        if (!isMounted) return;
        if (err instanceof UnauthorizedError) {
          navigate("/login", { replace: true });
          return;
        }
        if (err instanceof ApiError && err.status === 403) {
          setError("Нет доступа к онбордингу");
          return;
        }
        console.error("Не удалось получить статус онбординга", err);
        setError("Модуль онбординга временно недоступен");
      } finally {
        if (!isMounted) return;
        setIsLoading(false);
      }
    };
    void loadStatus();
    return () => {
      isMounted = false;
    };
  }, [navigate, user]);

  useEffect(() => {
    if (step !== "contract" || !user) return;
    if (contractReady) return;
    fetchContract(user)
      .then((data) => {
        setContractInfo(data);
        setContractReady(true);
      })
      .catch(() => {
        setContractReady(false);
      });
  }, [contractReady, step, user]);

  if (!SELF_SIGNUP_ENABLED) {
    return (
      <EmptyState
        title="Модуль недоступен"
        description="Онбординг клиента отключён."
        action={
          <button type="button" className="ghost neft-btn-secondary" onClick={() => navigate("/login")}>
            Вернуться к входу
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
    if (clientType === "LEGAL_ENTITY" && !kpp) {
      setError("КПП обязателен для юридических лиц");
      return;
    }
    if (clientType === "LEGAL_ENTITY" && !ogrn) {
      setError("ОГРН обязателен для юридических лиц");
      return;
    }
    if (clientType === "SOLE_PROPRIETOR" && !ogrnip) {
      setError("ОГРНИП обязателен для ИП");
      return;
    }
    setIsLoading(true);
    try {
      const response = await submitOnboardingProfile(user, {
        client_type: clientType,
        company_name: companyName,
        inn,
        kpp: clientType === "LEGAL_ENTITY" ? kpp : null,
        ogrn: clientType === "LEGAL_ENTITY" ? ogrn : null,
        ogrnip: clientType === "SOLE_PROPRIETOR" ? ogrnip : null,
        legal_address: legalAddress,
        contact_person: {
          full_name: contactName,
          position: contactRole,
          phone: contactPhone,
          email: contactEmail,
        },
      });
      setStatus(response.data);
      setStep(ONBOARDING_DOCS_REQUIRED ? "docs" : "contract");
      showToast("success", "Профиль сохранён");
    } catch (err) {
      console.error("Ошибка сохранения профиля", err);
      setError("Не удалось сохранить профиль");
      showToast("error", "Не удалось сохранить профиль");
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUpload = async () => {
    if (!user || !selectedFile) return;
    setIsLoading(true);
    try {
      const response = await uploadOnboardingFile(user, selectedFile, selectedFileType);
      setUploadedFiles((prev) => [
        ...prev,
        { name: selectedFile.name, type: selectedFileType, status: response.data.status ?? "uploaded" },
      ]);
      setSelectedFile(null);
      showToast("success", "Файл загружен");
    } catch (err) {
      console.error("Ошибка загрузки файла", err);
      showToast("error", "Не удалось загрузить файл");
    } finally {
      setIsLoading(false);
    }
  };

  const handleContractGenerate = async () => {
    if (!user) return;
    setIsLoading(true);
    try {
      const response = await generateContract(user);
      setContractInfo(response.data);
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
    try {
      const response = await signContract(user, { otp: otp.trim() });
      setStatus(response.data);
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
        <p className="muted">Шаг {step === "profile" ? 1 : step === "docs" ? 2 : step === "contract" ? 3 : 4} из 4</p>
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
                onChange={(e) => setClientType(e.target.value as ClientType)}
              >
                <option value="LEGAL_ENTITY">Юридическое лицо</option>
                <option value="SOLE_PROPRIETOR">ИП</option>
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
            {clientType === "LEGAL_ENTITY" ? (
              <label>
                КПП
                <input className="neft-input" value={kpp} onChange={(e) => setKpp(e.target.value)} />
              </label>
            ) : null}
            {clientType === "LEGAL_ENTITY" ? (
              <label>
                ОГРН
                <input className="neft-input" value={ogrn} onChange={(e) => setOgrn(e.target.value)} />
              </label>
            ) : null}
            {clientType === "SOLE_PROPRIETOR" ? (
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
        {step === "docs" ? (
          <div className="onboarding-form">
            <p className="muted">Загрузите необходимые документы.</p>
            <label>
              Тип документа
              <select
                className="neft-select neft-input"
                value={selectedFileType}
                onChange={(e) => setSelectedFileType(e.target.value)}
              >
                {FILE_TYPES.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Файл
              <input
                type="file"
                className="neft-input"
                onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              />
            </label>
            <button
              type="button"
              className="neft-button neft-btn-secondary"
              onClick={handleFileUpload}
              disabled={!selectedFile || isLoading}
            >
              Загрузить
            </button>
            {uploadedFiles.length > 0 ? (
              <ul className="onboarding-files">
                {uploadedFiles.map((file, index) => (
                  <li key={`${file.name}-${index}`}>
                    {file.name} · {file.status}
                  </li>
                ))}
              </ul>
            ) : null}
            <button type="button" className="neft-button neft-btn-primary" onClick={() => setStep("contract")}>
              Перейти к договору
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
                <div>{status?.status ?? "—"}</div>
              </div>
              <div>
                <div className="label">Статус договора</div>
                <div>{status?.contract_status ?? "SIGNED_SIMPLE"}</div>
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
