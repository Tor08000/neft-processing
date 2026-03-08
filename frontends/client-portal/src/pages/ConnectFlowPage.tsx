import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createOrg, fetchPlans, type SubscriptionPlan } from "../api/clientPortal";
import { useAuth } from "../auth/AuthContext";
import { useClient } from "../auth/ClientContext";
import { useClientJourney } from "../auth/ClientJourneyContext";

type CustomerType = "INDIVIDUAL" | "IP" | "LEGAL";

export function ConnectHomePage() {
  const { state } = useClientJourney();
  return (
    <div className="stack card neft-card">
      <h1>Подключение клиента</h1>
      <p>Статус подключения: {state}</p>
      <Link className="neft-button neft-btn-primary" to="/connect/plan">
        Продолжить подключение
      </Link>
    </div>
  );
}

export function ConnectPlanPage() {
  const { user } = useAuth();
  const { updateDraft } = useClientJourney();
  const navigate = useNavigate();
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);

  useEffect(() => {
    if (!user) return;
    void fetchPlans(user).then(setPlans).catch(() => setPlans([]));
  }, [user]);

  return (
    <div className="stack card neft-card">
      <h1>Выбор тарифа</h1>
      {(plans.length ? plans : [{ id: "stub", code: "START", title: "Start", is_active: true }]).map((plan) => (
        <button
          key={plan.code}
          className="neft-button neft-btn-secondary"
          onClick={() => {
            updateDraft({ selectedPlan: plan.code });
            navigate("/connect/type");
          }}
        >
          {plan.title} ({plan.code})
        </button>
      ))}
    </div>
  );
}

export function ConnectTypePage() {
  const { updateDraft } = useClientJourney();
  const navigate = useNavigate();
  const types: Array<{ code: CustomerType; label: string }> = [
    { code: "INDIVIDUAL", label: "Физическое лицо" },
    { code: "IP", label: "ИП" },
    { code: "LEGAL", label: "Юридическое лицо" },
  ];

  return (
    <div className="stack card neft-card">
      <h1>Тип клиента</h1>
      {types.map((type) => (
        <button
          key={type.code}
          className="neft-button neft-btn-secondary"
          onClick={() => {
            updateDraft({ customerType: type.code });
            navigate("/connect/profile");
          }}
        >
          {type.label}
        </button>
      ))}
    </div>
  );
}

export function ConnectProfilePage() {
  const { user } = useAuth();
  const { draft, updateDraft } = useClientJourney();
  const { refresh } = useClient();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [inn, setInn] = useState("");
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim() || !inn.trim()) {
      setError("Заполните обязательные поля");
      return;
    }
    if (user) {
      await createOrg(user, {
        org_type: draft.customerType ?? "LEGAL",
        name,
        inn,
        address: "—",
      });
      await refresh();
    }
    updateDraft({ profileCompleted: true, documentsGenerated: true });
    navigate("/connect/documents");
  };

  return (
    <form onSubmit={onSubmit} className="stack card neft-card">
      <h1>Профиль клиента</h1>
      {error ? <div role="alert">{error}</div> : null}
      <input className="neft-input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Название / ФИО" />
      <input className="neft-input" value={inn} onChange={(e) => setInn(e.target.value)} placeholder="ИНН" />
      <button type="submit" className="neft-button neft-btn-primary">Продолжить</button>
    </form>
  );
}

export function ConnectDocumentsPage() {
  const { updateDraft } = useClientJourney();
  const navigate = useNavigate();
  return (
    <div className="stack card neft-card">
      <h1>Документы</h1>
      <p>Договор оферты и согласия сформированы.</p>
      <button
        className="neft-button neft-btn-primary"
        onClick={() => {
          updateDraft({ documentsGenerated: true, documentsViewed: true });
          navigate("/connect/sign");
        }}
      >
        Я ознакомился
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
      <button
        className="neft-button neft-btn-primary"
        onClick={() => {
          updateDraft({ paymentStatus: "succeeded" });
          navigate("/dashboard");
        }}
      >
        Оплатить (демо)
      </button>
    </div>
  );
}
