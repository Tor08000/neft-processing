import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  clearOnboardingSession,
  createApplication,
  getApplication,
  getOnboardingSession,
  saveOnboardingSession,
  submitApplication,
  updateApplication,
  type OnboardingApplication,
} from "../api/onboarding";
import { ApiError } from "../api/http";

export function OnboardingSelfRegistrationPage({ mode }: { mode: "start" | "form" | "status" }) {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [inn, setInn] = useState("");
  const [orgType, setOrgType] = useState("");
  const [phone, setPhone] = useState("");
  const [ogrn, setOgrn] = useState("");
  const [application, setApplication] = useState<OnboardingApplication | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const session = useMemo(() => getOnboardingSession(), []);

  const loadApplication = async () => {
    if (!session.appId || !session.accessToken) return;
    try {
      const app = await getApplication(session.appId, session.accessToken);
      setApplication(app);
      setEmail(app.email ?? "");
      setCompanyName(app.company_name ?? "");
      setInn(app.inn ?? "");
      setOrgType(app.org_type ?? "");
      setPhone(app.phone ?? "");
      setOgrn(app.ogrn ?? "");
    } catch (e) {
      if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
        clearOnboardingSession();
        setError("Сессия заявки истекла, создайте новую заявку.");
        return;
      }
      throw e;
    }
  };

  useEffect(() => {
    void loadApplication();
  }, []);

  const onCreate = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await createApplication({ email });
      saveOnboardingSession(res.application.id, res.access_token);
      navigate("/client/onboarding/form");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось создать заявку");
    } finally {
      setBusy(false);
    }
  };

  const onSave = async () => {
    if (!session.appId || !session.accessToken) {
      setError("Нет активной заявки. Создайте новую заявку.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const app = await updateApplication(
        session.appId,
        { company_name: companyName, inn, org_type: orgType, phone, ogrn },
        session.accessToken,
      );
      setApplication(app);
    } catch (e) {
      if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
        clearOnboardingSession();
      }
      setError(e instanceof Error ? e.message : "Не удалось сохранить заявку");
    } finally {
      setBusy(false);
    }
  };

  const onSubmit = async () => {
    if (!session.appId || !session.accessToken) return;
    setBusy(true);
    setError(null);
    try {
      await onSave();
      const app = await submitApplication(session.appId, session.accessToken);
      setApplication(app);
      navigate("/client/onboarding/status");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось отправить заявку");
    } finally {
      setBusy(false);
    }
  };

  if (mode === "start") {
    return (
      <main style={{ maxWidth: 640, margin: "40px auto", padding: 16 }}>
        <h1>Создание заявки</h1>
        <form onSubmit={onCreate}>
          <label>
            Email
            <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <div style={{ marginTop: 12 }}>
            <button disabled={busy} type="submit">
              Создать заявку
            </button>
          </div>
        </form>
        {error ? <p>{error}</p> : null}
      </main>
    );
  }

  if (mode === "form") {
    return (
      <main style={{ maxWidth: 640, margin: "40px auto", padding: 16 }}>
        <h1>Анкета заявки</h1>
        <p>Application ID: {session.appId ?? "—"}</p>
        <label>Название компании<input value={companyName} onChange={(e) => setCompanyName(e.target.value)} /></label>
        <label>ИНН<input value={inn} onChange={(e) => setInn(e.target.value)} /></label>
        <label>Орг. форма<input value={orgType} onChange={(e) => setOrgType(e.target.value)} /></label>
        <label>Телефон<input value={phone} onChange={(e) => setPhone(e.target.value)} /></label>
        <label>ОГРН (опц.)<input value={ogrn} onChange={(e) => setOgrn(e.target.value)} /></label>
        <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
          <button disabled={busy} type="button" onClick={() => void onSave()}>
            Сохранить
          </button>
          <button disabled={busy} type="button" onClick={() => void onSubmit()}>
            Отправить
          </button>
        </div>
        <p>
          <Link to="/client/onboarding/status">К статусу</Link>
        </p>
        {error ? <p>{error}</p> : null}
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 640, margin: "40px auto", padding: 16 }}>
      <h1>Статус заявки</h1>
      <p>Текущий статус: {application?.status ?? "DRAFT"}</p>
      <ol>
        <li>Draft</li>
        <li>Submitted</li>
        <li>In review</li>
        <li>Approved</li>
        <li>Rejected</li>
      </ol>
      {application?.status === "DRAFT" ? <Link to="/client/onboarding/form">Редактировать</Link> : null}
      {error ? <p>{error}</p> : null}
    </main>
  );
}
