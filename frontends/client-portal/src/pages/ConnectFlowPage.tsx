import { FormEvent, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createOrg } from "../api/clientPortal";
import { useAuth } from "../auth/AuthContext";
import { useClient } from "../auth/ClientContext";
import { useClientJourney } from "../auth/ClientJourneyContext";

type CustomerType = "INDIVIDUAL" | "SOLE_PROPRIETOR" | "LEGAL_ENTITY";

export type ConnectProfileField =
  | "fullName"
  | "legalName"
  | "phone"
  | "email"
  | "inn"
  | "kpp"
  | "ogrn"
  | "ogrnip"
  | "address"
  | "contact";

type ConnectProfileValues = Record<ConnectProfileField, string>;
type ConnectProfileErrors = Partial<Record<ConnectProfileField, string>>;

type PlanConfig = {
  code: string;
  title: string;
  monthly: string;
  discount: string;
  summary: string;
  limits: string;
};

const PLAN_OPTIONS: PlanConfig[] = [
  { code: "START", title: "Start", monthly: "₽2 900 / мес", discount: "-10% при годовой оплате", summary: "Базовый кабинет", limits: "До 20 карт" },
  { code: "BUSINESS", title: "Business", monthly: "₽7 900 / мес", discount: "-15% при годовой оплате", summary: "Карты + аналитика + документы", limits: "До 150 карт" },
  { code: "ENTERPRISE", title: "Enterprise", monthly: "Индивидуально", discount: "Персональные условия", summary: "Все модули и расширенные лимиты", limits: "Без лимитов" },
];

export function ConnectHomePage() {
  const { state, nextRoute } = useClientJourney();
  return (
    <div className="stack card neft-card">
      <h1>Подключение клиента</h1>
      <p>Текущий этап: {state}</p>
      <p className="muted">Для полного доступа завершите подключение компании и оплату тарифа.</p>
      <Link className="neft-button neft-btn-primary" to={nextRoute === "/connect" ? "/connect/plan" : nextRoute}>
        Продолжить подключение
      </Link>
    </div>
  );
}

export function ConnectPlanPage() {
  const { updateDraft } = useClientJourney();
  const navigate = useNavigate();

  return (
    <div className="stack card neft-card">
      <h1>Выбор тарифа</h1>
      {PLAN_OPTIONS.map((plan) => (
        <div key={plan.code} className="card neft-card stack">
          <h2>{plan.title}</h2>
          <div>{plan.monthly}</div>
          <div className="muted">{plan.discount}</div>
          <div>{plan.summary}</div>
          <div className="muted">{plan.limits}</div>
          <button
            className="neft-button neft-btn-primary"
            onClick={() => {
              updateDraft({ selectedPlan: plan.code });
              navigate("/connect/type");
            }}
          >
            Выбрать {plan.title}
          </button>
        </div>
      ))}
    </div>
  );
}

export function ConnectTypePage() {
  const { updateDraft } = useClientJourney();
  const navigate = useNavigate();
  const types: Array<{ code: CustomerType; label: string }> = [
    { code: "INDIVIDUAL", label: "Физическое лицо" },
    { code: "SOLE_PROPRIETOR", label: "Индивидуальный предприниматель" },
    { code: "LEGAL_ENTITY", label: "Юридическое лицо" },
  ];

  return (
    <div className="stack card neft-card">
      <h1>Тип клиента</h1>
      {types.map((type) => (
        <button
          key={type.code}
          className="neft-button neft-btn-secondary"
          onClick={() => {
            updateDraft({ customerType: type.code, profileCompleted: false });
            navigate("/connect/profile");
          }}
        >
          {type.label}
        </button>
      ))}
    </div>
  );
}

export function getProfileFields(customerType: CustomerType | null | undefined): ConnectProfileField[] {
  if (customerType === "INDIVIDUAL") {
    return ["fullName", "phone", "email", "address"];
  }
  if (customerType === "SOLE_PROPRIETOR") {
    return ["fullName", "inn", "ogrnip", "address", "contact"];
  }
  return ["legalName", "inn", "kpp", "ogrn", "address", "contact"];
}

export function ConnectProfilePage() {
  const { user } = useAuth();
  const { draft, updateDraft } = useClientJourney();
  const { refresh } = useClient();
  const navigate = useNavigate();

  const [values, setValues] = useState<ConnectProfileValues>({
    fullName: "",
    legalName: "",
    phone: "",
    email: user?.email ?? "",
    address: "",
    inn: "",
    kpp: "",
    ogrn: "",
    ogrnip: "",
    contact: "",
  });
  const [errors, setErrors] = useState<ConnectProfileErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);

  const requiredFields = useMemo(() => getProfileFields(draft.customerType), [draft.customerType]);

  const setField = (field: ConnectProfileField, value: string) => {
    setValues((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: "" }));
  };

  const validate = () => {
    const nextErrors: ConnectProfileErrors = {};
    requiredFields.forEach((field) => {
      if (!values[field]?.trim()) {
        nextErrors[field] = "Обязательное поле";
      }
    });
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitError(null);
    if (!validate()) return;

    if (!draft.customerType) {
      setSubmitError("Сначала выберите тип клиента");
      return;
    }

    try {
      if (user) {
        const orgType = draft.customerType === "LEGAL_ENTITY" ? "LEGAL" : draft.customerType === "SOLE_PROPRIETOR" ? "IP" : "INDIVIDUAL";
        const name = draft.customerType === "LEGAL_ENTITY" ? values.legalName : values.fullName;
        await createOrg(user, {
          org_type: orgType,
          name,
          inn: values.inn || "-",
          kpp: values.kpp || null,
          ogrn: values.ogrn || values.ogrnip || null,
          address: values.address || null,
        });
        await refresh();
      }

      updateDraft({ profileCompleted: true, documentsGenerated: false, documentsViewed: false });
      navigate("/connect/documents");
    } catch {
      setSubmitError("Не удалось сохранить профиль. Проверьте поля и попробуйте снова.");
    }
  };

  if (!draft.customerType) {
    return (
      <div className="stack card neft-card">
        <h1>Профиль клиента</h1>
        <p>Сначала выберите тип клиента.</p>
        <Link to="/connect/type" className="neft-button neft-btn-primary">Выбрать тип</Link>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="stack card neft-card">
      <h1>Профиль клиента</h1>
      {submitError ? <div role="alert">{submitError}</div> : null}

      {requiredFields.includes("fullName") ? <input className="neft-input" value={values.fullName} onChange={(e) => setField("fullName", e.target.value)} placeholder="ФИО" aria-invalid={Boolean(errors.fullName)} /> : null}
      {requiredFields.includes("legalName") ? <input className="neft-input" value={values.legalName} onChange={(e) => setField("legalName", e.target.value)} placeholder="Полное наименование" aria-invalid={Boolean(errors.legalName)} /> : null}
      {requiredFields.includes("phone") ? <input className="neft-input" value={values.phone} onChange={(e) => setField("phone", e.target.value)} placeholder="Телефон" aria-invalid={Boolean(errors.phone)} /> : null}
      {requiredFields.includes("email") ? <input className="neft-input" value={values.email} onChange={(e) => setField("email", e.target.value)} placeholder="Email" aria-invalid={Boolean(errors.email)} /> : null}
      {requiredFields.includes("inn") ? <input className="neft-input" value={values.inn} onChange={(e) => setField("inn", e.target.value)} placeholder="ИНН" aria-invalid={Boolean(errors.inn)} /> : null}
      {requiredFields.includes("kpp") ? <input className="neft-input" value={values.kpp} onChange={(e) => setField("kpp", e.target.value)} placeholder="КПП" aria-invalid={Boolean(errors.kpp)} /> : null}
      {requiredFields.includes("ogrn") ? <input className="neft-input" value={values.ogrn} onChange={(e) => setField("ogrn", e.target.value)} placeholder="ОГРН" aria-invalid={Boolean(errors.ogrn)} /> : null}
      {requiredFields.includes("ogrnip") ? <input className="neft-input" value={values.ogrnip} onChange={(e) => setField("ogrnip", e.target.value)} placeholder="ОГРНИП" aria-invalid={Boolean(errors.ogrnip)} /> : null}
      {requiredFields.includes("address") ? <input className="neft-input" value={values.address} onChange={(e) => setField("address", e.target.value)} placeholder="Адрес" aria-invalid={Boolean(errors.address)} /> : null}
      {requiredFields.includes("contact") ? <input className="neft-input" value={values.contact} onChange={(e) => setField("contact", e.target.value)} placeholder="Контактное лицо" aria-invalid={Boolean(errors.contact)} /> : null}

      {Object.values(errors).filter(Boolean).length > 0 ? <div role="alert">Заполните обязательные поля.</div> : null}
      <button type="submit" className="neft-button neft-btn-primary">Продолжить</button>
    </form>
  );
}

export function ConnectDocumentsPage() {
  const { draft, updateDraft } = useClientJourney();
  const navigate = useNavigate();

  return (
    <div className="stack card neft-card">
      <h1>Документы</h1>
      <p>Пакет документов сформирован в режиме черновика.</p>
      <p className="muted">Статус: {draft.documentsGenerated ? "generated" : "not-generated"}</p>
      <button
        className="neft-button neft-btn-secondary"
        onClick={() => updateDraft({ documentsGenerated: true })}
      >
        Сгенерировать документы
      </button>
      <button
        className="neft-button neft-btn-primary"
        onClick={() => {
          updateDraft({ documentsGenerated: true, documentsViewed: true });
          navigate("/connect/sign");
        }}
      >
        Я ознакомился, перейти к подписанию
      </button>
    </div>
  );
}

export function ConnectSignPage() {
  const { updateDraft } = useClientJourney();
  const navigate = useNavigate();
  return (
    <div className="stack card neft-card">
      <h1>Подписание</h1>
      <p className="muted">Интеграция e-sign пока в режиме stub.</p>
      <button
        className="neft-button neft-btn-primary"
        onClick={() => {
          updateDraft({ documentsSigned: true, paymentStatus: "pending" });
          navigate("/connect/payment");
        }}
      >
        Подписать и продолжить
      </button>
    </div>
  );
}

export function ConnectPaymentPage() {
  const { draft, updateDraft } = useClientJourney();
  const navigate = useNavigate();
  return (
    <div className="stack card neft-card">
      <h1>Оплата подписки</h1>
      <p>Тариф: {draft.selectedPlan ?? "не выбран"}</p>
      <p>Статус оплаты: {draft.paymentStatus ?? "not-started"}</p>
      <button className="neft-button neft-btn-secondary" onClick={() => updateDraft({ paymentStatus: "failed" })}>
        Эмулировать ошибку оплаты
      </button>
      <button
        className="neft-button neft-btn-primary"
        onClick={() => {
          updateDraft({ paymentStatus: "succeeded" });
          navigate("/dashboard");
        }}
      >
        Оплатить
      </button>
    </div>
  );
}
