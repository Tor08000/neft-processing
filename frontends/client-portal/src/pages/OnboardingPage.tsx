import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
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
import { AppErrorState, AppForbiddenState, AppLoadingState } from "../components/states";
import { isDemoClient } from "@shared/demo/demo";
import { ApiError, CORE_API_BASE, UnauthorizedError, ValidationError } from "../api/http";
import { clearTokens, isValidJwt } from "../lib/apiClient";

type Step = "profile" | "plan" | "contract" | "activation";

const STEP_ORDER: Record<Step, number> = {
  profile: 0,
  plan: 1,
  contract: 2,
  activation: 3,
};

type StepDecisionSource = "backendState" | "profileSubmit" | "planSubmit" | "contractSubmit";

function getStepWithFloor(candidate: Step, floor: Step): Step {
  return STEP_ORDER[candidate] < STEP_ORDER[floor] ? floor : candidate;
}

function resolveStepFromAccessState(accessState?: string | null): Step | null {
  if (accessState === AccessState.ACTIVE) return "activation";
  if (accessState === AccessState.NEEDS_CONTRACT) return "contract";
  if (accessState === AccessState.NEEDS_PLAN) return "plan";
  if (accessState === AccessState.NEEDS_ONBOARDING) return "profile";
  return null;
}

type ProfileField =
  | "companyName"
  | "inn"
  | "kpp"
  | "ogrn"
  | "legalAddress"
  | "contactName"
  | "contactRole"
  | "contactPhone"
  | "contactEmail";

type ProfileFieldErrors = Partial<Record<ProfileField, string>>;

const PROFILE_BACKEND_FIELD_MAP: Record<string, ProfileField> = {
  name: "companyName",
  company_name: "companyName",
  organization_name: "companyName",
  inn: "inn",
  kpp: "kpp",
  ogrn: "ogrn",
  legal_address: "legalAddress",
  address: "legalAddress",
  contact_name: "contactName",
  contact_role: "contactRole",
  contact_phone: "contactPhone",
  contact_email: "contactEmail",
};

const DIGITS_ONLY_RE = /^\d+$/;

type BackendValidationItem = {
  field: string;
  message: string;
};

function parseBackendValidationErrors(detail: unknown): BackendValidationItem[] {
  if (!detail || typeof detail !== "object") return [];
  const body = detail as Record<string, unknown>;
  const entries = [body.detail, body.errors].filter(Array.isArray).flat() as unknown[];
  const parsed: BackendValidationItem[] = [];

  for (const entry of entries) {
    if (!entry || typeof entry !== "object") continue;
    const item = entry as Record<string, unknown>;
    const loc = Array.isArray(item.loc) ? item.loc.map((v) => String(v)) : [];
    const backendFieldRaw =
      typeof item.field === "string"
        ? item.field
        : typeof item.loc === "string"
          ? item.loc
          : loc.length > 0
            ? loc[loc.length - 1]
            : "";
    const backendField = backendFieldRaw.replace(/^body\./, "").trim();
    const message =
      typeof item.message === "string"
        ? item.message
        : typeof item.msg === "string"
          ? item.msg
          : typeof item.detail === "string"
            ? item.detail
            : "Некорректное значение";

    if (backendField) {
      parsed.push({ field: backendField, message });
    }
  }

  return parsed;
}

const getApiErrorMessage = (error: ApiError): string => {
  const detail = error.detail;
  if (typeof detail === "string" && detail.trim() !== "") {
    return detail;
  }
  if (detail && typeof detail === "object") {
    const maybeDetail = (detail as Record<string, unknown>).detail;
    const maybeReason = (detail as Record<string, unknown>).reason;
    const maybeMessage = (detail as Record<string, unknown>).message;
    if (typeof maybeDetail === "string" && maybeDetail.trim() !== "") return maybeDetail;
    if (typeof maybeReason === "string" && maybeReason.trim() !== "") return maybeReason;
    if (typeof maybeMessage === "string" && maybeMessage.trim() !== "") return maybeMessage;
  }
  return error.message || "Не удалось сохранить профиль";
};

function validateProfile(params: {
  clientType: "LEGAL" | "IP" | "INDIVIDUAL";
  companyName: string;
  inn: string;
  kpp: string;
  ogrn: string;
  legalAddress: string;
}): { fieldErrors: ProfileFieldErrors; innWarning: string | null } {
  const fieldErrors: ProfileFieldErrors = {};
  let innWarning: string | null = null;
  const innTrimmed = params.inn.trim();
  const kppTrimmed = params.kpp.trim();
  const ogrnTrimmed = params.ogrn.trim();

  if (!params.companyName.trim()) {
    fieldErrors.companyName = "Заполните обязательное поле";
  }
  if (!innTrimmed) {
    fieldErrors.inn = "Заполните обязательное поле";
  } else {
    if (!DIGITS_ONLY_RE.test(innTrimmed)) {
      fieldErrors.inn = "Ожидаются только цифры";
    } else if (innTrimmed.length !== 10 && innTrimmed.length !== 12) {
      fieldErrors.inn = "ИНН должен содержать 10 или 12 цифр";
    } else if (params.clientType === "LEGAL" && innTrimmed.length === 12) {
      innWarning = "Для юрлица обычно используется ИНН из 10 цифр";
    }
  }

  if (!params.legalAddress.trim()) {
    fieldErrors.legalAddress = "Заполните обязательное поле";
  }

  if (params.clientType === "LEGAL") {
    if (!kppTrimmed) {
      fieldErrors.kpp = "Заполните обязательное поле";
    } else if (!DIGITS_ONLY_RE.test(kppTrimmed)) {
      fieldErrors.kpp = "Ожидаются только цифры";
    } else if (kppTrimmed.length !== 9) {
      fieldErrors.kpp = "КПП должен содержать 9 цифр";
    }

    if (!ogrnTrimmed) {
      fieldErrors.ogrn = "Заполните обязательное поле";
    } else if (!DIGITS_ONLY_RE.test(ogrnTrimmed)) {
      fieldErrors.ogrn = "Ожидаются только цифры";
    } else if (ogrnTrimmed.length !== 13) {
      fieldErrors.ogrn = "ОГРН должен содержать 13 цифр";
    }
  }

  return { fieldErrors, innWarning };
}

export function OnboardingPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const { client, refresh, portalState, error: portalError, isLoading: isPortalLoading } = useClient();
  const { toast, showToast } = useToast();
  const [step, setStep] = useState<Step>("profile");
  const [isLoading, setIsLoading] = useState(false);
  const minAllowedStepRef = useRef<Step>("profile");
  const resolveStep = (candidateStep: Step, source: StepDecisionSource): Step => {
    const minAllowedStep = minAllowedStepRef.current;
    const resolvedStep = getStepWithFloor(candidateStep, minAllowedStep);
    if (import.meta.env.DEV && resolvedStep !== candidateStep) {
      console.info("[onboarding:step:resolve] ignored_regression", {
        source,
        candidate_step: candidateStep,
        resolved_step: resolvedStep,
        min_allowed_step: minAllowedStep,
      });
    }
    if (import.meta.env.DEV) {
      console.info("[onboarding:step:resolve] decision", {
        source,
        candidate_step: candidateStep,
        resolved_step: resolvedStep,
        min_allowed_step: minAllowedStep,
      });
    }
    return resolvedStep;
  };
  const [isSubmitting, setIsSubmitting] = useState(false);
  const hasInitializedRef = useRef(false);
  const hasRefreshedOnMountRef = useRef(false);
  const reauthRedirectedRef = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const [profileFieldErrors, setProfileFieldErrors] = useState<ProfileFieldErrors>({});
  const [innWarning, setInnWarning] = useState<string | null>(null);
  const onboardingEnabled = client?.gating?.onboarding_enabled ?? client?.features?.onboarding_enabled ?? SELF_SIGNUP_ENABLED;
  const isDemoClientAccount = isDemoClient(user?.email ?? client?.user?.email ?? null);
  const hasProfile = Boolean(client?.org?.id || client?.org?.name || client?.org_status);

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
    if (!import.meta.env.DEV) return;
    console.info("[onboarding:lifecycle] mounted", {
      route: location.pathname,
      portal_state: portalState,
      access_state: client?.access_state ?? null,
    });
    return () => {
      console.info("[onboarding:lifecycle] unmounted", { route: location.pathname });
    };
  }, []);

  useEffect(() => {
    if (!user || !onboardingEnabled) return;
    if (hasInitializedRef.current) return;
    hasInitializedRef.current = true;
    if (import.meta.env.DEV) {
      console.info("[onboarding:init] started", {
        route: location.pathname,
        portal_state: portalState,
        has_profile: hasProfile,
      });
    }
    if (portalState === "READY" && !hasProfile && !hasRefreshedOnMountRef.current) {
      hasRefreshedOnMountRef.current = true;
      if (import.meta.env.DEV) {
        console.info("[onboarding:init] refresh_called", {
          route: location.pathname,
          portal_state: portalState,
        });
      }
      void refresh()
        .then(() => {
          if (import.meta.env.DEV) {
            console.info("[onboarding:init] refresh_resolved", {
              route: location.pathname,
              portal_state: portalState,
            });
          }
        })
        .catch((initRefreshError) => {
          if (import.meta.env.DEV) {
            console.info("[onboarding:init] refresh_failed", {
              error_type: initRefreshError instanceof Error ? initRefreshError.name : typeof initRefreshError,
            });
          }
        })
        .finally(() => {
          if (import.meta.env.DEV) {
            console.info("[onboarding:init] completed", {
              route: location.pathname,
              portal_state: portalState,
            });
          }
        });
      return;
    }
    if (import.meta.env.DEV) {
      console.info("[onboarding:init] completed", {
        route: location.pathname,
        portal_state: portalState,
      });
    }
  }, [hasProfile, location.pathname, onboardingEnabled, portalState, refresh, user]);

  useEffect(() => {
    if (!import.meta.env.DEV) return;
    console.info("[onboarding:step:change]", {
      step,
      min_allowed_step: minAllowedStepRef.current,
      access_state: client?.access_state ?? null,
    });
  }, [client?.access_state, step]);

  useEffect(() => {
    if (!user || !onboardingEnabled) return;
    const nextStep = resolveStepFromAccessState(client?.access_state);
    if (!nextStep) return;
    setStep((currentStep) => {
      const candidateStep = STEP_ORDER[nextStep] > STEP_ORDER[currentStep] ? nextStep : currentStep;
      return resolveStep(candidateStep, "backendState");
    });
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

  if (portalState === "LOADING" || isPortalLoading) {
    return <AppLoadingState label="Загружаем профиль клиента..." />;
  }

  if (portalState === "AUTH_REQUIRED") {
    return <Navigate to="/login" replace />;
  }

  if (isDemoClientAccount && !onboardingEnabled) {
    return (
      <EmptyState
        title="Демо-режим: онбординг пропущен"
        description="В демонстрационной среде подключение компании не требуется."
        action={
          <button type="button" className="ghost neft-btn-secondary" onClick={() => navigate("/dashboard")}>
            Перейти в кабинет
          </button>
        }
      />
    );
  }

  if (portalState === "READY" && hasProfile) {
    if (import.meta.env.DEV) {
      console.info("[onboarding:redirect] already_has_profile", {
        from: location.pathname,
        to: "/",
        access_state: client?.access_state ?? null,
      });
    }
    return <Navigate to="/" replace />;
  }

  if (portalState === "FORBIDDEN") {
    return <AppForbiddenState message="Недостаточно прав для подключения клиента." />;
  }

  if (portalState === "SERVICE_UNAVAILABLE") {
    return (
      <AppErrorState
        message="Сервис временно недоступен. Попробуйте позже."
        onRetry={refresh}
        status={portalError?.status}
      />
    );
  }

  if (portalState === "NETWORK_DOWN") {
    return (
      <AppErrorState
        message="Нет соединения с сервером. Проверьте подключение к интернету."
        onRetry={refresh}
        status={portalError?.status}
      />
    );
  }

  if (portalState === "API_MISCONFIGURED") {
    return (
      <AppErrorState
        message="Маршрут портала недоступен. Проверьте настройки API."
        onRetry={refresh}
        status={portalError?.status}
      />
    );
  }

  if (portalState === "ERROR_FATAL") {
    return (
      <AppErrorState
        message={portalError?.message ?? "Не удалось загрузить профиль клиента."}
        onRetry={refresh}
        status={portalError?.status}
      />
    );
  }

  if (
    client?.access_state &&
    ![AccessState.NEEDS_ONBOARDING, AccessState.NEEDS_PLAN, AccessState.NEEDS_CONTRACT].includes(
      client.access_state as AccessState,
    )
  ) {
    if (import.meta.env.DEV) {
      console.info("[onboarding:redirect] access_state_not_onboarding", {
        from: location.pathname,
        to: "/",
        access_state: client.access_state,
      });
    }
    return <Navigate to="/" replace />;
  }

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
    setInnWarning(null);
    setProfileFieldErrors({});
    if (!user) return;

    if (import.meta.env.DEV) {
      console.info("[onboarding:submit:profile] start", {
        step,
        client_type: clientType,
      });
    }

    const validation = validateProfile({
      clientType,
      companyName,
      inn,
      kpp,
      ogrn,
      legalAddress,
    });

    setProfileFieldErrors(validation.fieldErrors);
    setInnWarning(validation.innWarning);

    if (import.meta.env.DEV) {
      console.info("[onboarding:submit:profile] validation", {
        has_errors: Object.keys(validation.fieldErrors).length > 0,
        invalid_fields: Object.keys(validation.fieldErrors),
      });
    }

    if (Object.keys(validation.fieldErrors).length > 0) {
      setError("Проверьте корректность заполнения полей");
      return;
    }

    const payload = {
      org_type: clientType,
      name: companyName.trim(),
      inn: inn.trim(),
      kpp: clientType === "LEGAL" ? kpp.trim() : null,
      ogrn: clientType === "LEGAL" ? ogrn.trim() : null,
      address: legalAddress.trim(),
    };

    if (import.meta.env.DEV) {
      const token = user?.token;
      const hasValidAuthorization = typeof token === "string" && isValidJwt(token);
      console.info("[onboarding:submit:profile] request", {
        payload_keys: Object.keys(payload),
        api_url: `${CORE_API_BASE}/client/onboarding/profile`,
        authorization_attached: hasValidAuthorization,
        token_length: hasValidAuthorization ? token.length : 0,
      });
    }

    setIsSubmitting(true);
    setIsLoading(true);
    const stepBeforeSubmit = step;
    try {
      const response = await createOrg(user, payload);
      minAllowedStepRef.current = "plan";
      setStep((currentStep) => {
        const candidateStep = STEP_ORDER[currentStep] < STEP_ORDER["plan"] ? "plan" : currentStep;
        const nextStep = resolveStep(candidateStep, "profileSubmit");
        if (import.meta.env.DEV) {
          console.info("[onboarding:submit:profile] step_transition", {
            step_before_submit: stepBeforeSubmit,
            current_step: currentStep,
            next_step: nextStep,
          });
        }
        return nextStep;
      });
      if (import.meta.env.DEV) {
        console.info("[onboarding:submit:profile] response", {
          status: response.status,
          body: response.data ?? null,
        });
        console.info("[onboarding:submit:profile] step_after_submit", {
          min_allowed_step: minAllowedStepRef.current,
          next_step: "plan",
        });
      }
      try {
        await refresh();
        if (import.meta.env.DEV) {
          console.info("[onboarding:submit:profile] step_after_refresh", {
            min_allowed_step: minAllowedStepRef.current,
          });
        }
      } catch (refreshError) {
        if (import.meta.env.DEV) {
          console.info("[onboarding:submit:profile] refresh_after_success_failed", {
            error_type: refreshError instanceof Error ? refreshError.name : typeof refreshError,
          });
        }
      }
      showToast("success", "Профиль сохранён");
    } catch (err) {
      console.error("Ошибка сохранения профиля", err);
      if (err instanceof UnauthorizedError) {
        if (import.meta.env.DEV) {
          console.info("[onboarding:submit:profile] response", { status: 401, body: { message: err.message } });
        }
        setError("Требуется повторный вход");
        showToast("error", "Требуется повторный вход");
        if (!reauthRedirectedRef.current) {
          reauthRedirectedRef.current = true;
          clearTokens();
          window.location.replace("/client/login?reauth=1");
        }
        return;
      }
      if (err instanceof ValidationError) {
        const detail = err.details as Record<string, unknown> | string | undefined;
        const fieldMap: ProfileFieldErrors = {};
        const backendValidationErrors = parseBackendValidationErrors(detail);
        for (const item of backendValidationErrors) {
          const mappedField = PROFILE_BACKEND_FIELD_MAP[item.field];
          if (mappedField && !fieldMap[mappedField]) {
            fieldMap[mappedField] = item.message;
          }
        }

        if (import.meta.env.DEV) {
          console.info("[onboarding:submit:profile] response", { status: 422, body: err.details });
          console.info("[onboarding:submit:profile] validation_mapping", {
            status: 422,
            backend_fields: backendValidationErrors.map((item) => item.field),
            mapped_frontend_fields: Object.keys(fieldMap),
          });
        }

        if (Object.keys(fieldMap).length > 0) {
          setProfileFieldErrors(fieldMap);
        } else if (import.meta.env.DEV) {
          console.info("[onboarding:submit:profile] unmapped_validation_details", {
            raw_details: err.details,
          });
        }
        const validationMessage =
          typeof detail === "string" && detail.trim() !== ""
            ? detail
            : typeof detail === "object" && detail && typeof (detail as { detail?: unknown }).detail === "string"
              ? String((detail as { detail?: unknown }).detail)
              : "Ошибка валидации. Проверьте данные формы";
        setError(validationMessage);
        showToast("error", validationMessage);
        return;
      }
      if (err instanceof ApiError) {
        if (import.meta.env.DEV) {
          console.info("[onboarding:submit:profile] response", { status: err.status, body: err.detail ?? err.message });
          if (!err.detail) {
            console.info("[onboarding:submit:profile] unmapped_backend_message", { message: err.message });
          }
        }
        const message = err.status >= 500 ? "Сервис временно недоступен" : getApiErrorMessage(err);
        setError(message);
        showToast("error", message);
        return;
      }
      setError("Сервис временно недоступен, попробуйте позже");
      if (import.meta.env.DEV) {
        console.info("[onboarding:submit:profile] response", { status: "unknown", body: "unexpected_error" });
      }
      showToast("error", "Сервис временно недоступен, попробуйте позже");
    } finally {
      setIsSubmitting(false);
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
      minAllowedStepRef.current = "contract";
      setStep((currentStep) =>
        resolveStep(STEP_ORDER[currentStep] < STEP_ORDER["contract"] ? "contract" : currentStep, "planSubmit"),
      );
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
      minAllowedStepRef.current = "activation";
      setStep((currentStep) =>
        resolveStep(
          STEP_ORDER[currentStep] < STEP_ORDER["activation"] ? "activation" : currentStep,
          "contractSubmit",
        ),
      );
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
              {profileFieldErrors.companyName ? <div className="error">{profileFieldErrors.companyName}</div> : null}
            </label>
            <label>
              ИНН
              <input className="neft-input" value={inn} onChange={(e) => setInn(e.target.value)} />
              {profileFieldErrors.inn ? <div className="error">{profileFieldErrors.inn}</div> : null}
              {innWarning ? <div className="muted">{innWarning}</div> : null}
            </label>
            {clientType === "LEGAL" ? (
              <label>
                КПП
                <input className="neft-input" value={kpp} onChange={(e) => setKpp(e.target.value)} />
                {profileFieldErrors.kpp ? <div className="error">{profileFieldErrors.kpp}</div> : null}
              </label>
            ) : null}
            {clientType === "LEGAL" ? (
              <label>
                ОГРН
                <input className="neft-input" value={ogrn} onChange={(e) => setOgrn(e.target.value)} />
                {profileFieldErrors.ogrn ? <div className="error">{profileFieldErrors.ogrn}</div> : null}
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
              {profileFieldErrors.legalAddress ? <div className="error">{profileFieldErrors.legalAddress}</div> : null}
            </label>
            <div className="onboarding-section">
              <h3>Контактное лицо</h3>
              <label>
                ФИО (необязательно)
                <input className="neft-input" value={contactName} onChange={(e) => setContactName(e.target.value)} />
                {profileFieldErrors.contactName ? <div className="error">{profileFieldErrors.contactName}</div> : null}
              </label>
              <label>
                Должность (необязательно)
                <input className="neft-input" value={contactRole} onChange={(e) => setContactRole(e.target.value)} />
                {profileFieldErrors.contactRole ? <div className="error">{profileFieldErrors.contactRole}</div> : null}
              </label>
              <label>
                Телефон (необязательно)
                <input className="neft-input" value={contactPhone} onChange={(e) => setContactPhone(e.target.value)} />
                {profileFieldErrors.contactPhone ? <div className="error">{profileFieldErrors.contactPhone}</div> : null}
              </label>
              <label>
                Email (необязательно)
                <input className="neft-input" value={contactEmail} onChange={(e) => setContactEmail(e.target.value)} />
                {profileFieldErrors.contactEmail ? <div className="error">{profileFieldErrors.contactEmail}</div> : null}
              </label>
            </div>
            <button type="submit" className="neft-button neft-btn-primary" disabled={isSubmitting}>
              {isSubmitting ? <span className="neft-spinner" aria-hidden /> : null}
              {isSubmitting ? "Сохраняем..." : "Продолжить"}
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
