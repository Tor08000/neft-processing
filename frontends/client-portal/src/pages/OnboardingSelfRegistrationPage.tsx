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
import {
  createDocumentsPackage,
  downloadDocumentsPackage,
  downloadGeneratedOnboardingDocument,
  getDocumentsPackageStatus,
  downloadOnboardingDocument,
  generateOnboardingDocuments,
  listGeneratedOnboardingDocuments,
  listOnboardingDocuments,
  uploadOnboardingDocument,
  type GeneratedOnboardingDocumentItem,
  type OnboardingDocStatus,
  type OnboardingDocType,
  type OnboardingDocumentItem,
} from "../api/onboardingDocuments";
import { ApiError } from "../api/http";

const REQUIRED_DOC_TYPES: { type: OnboardingDocType; label: string }[] = [
  { type: "CHARTER", label: "Устав" },
  { type: "EGRUL", label: "Выписка ЕГРЮЛ/ЕГРИП" },
  { type: "PASSPORT", label: "Паспорт/данные представителя" },
  { type: "POWER_OF_ATTORNEY", label: "Доверенность" },
  { type: "BANK_DETAILS", label: "Банковские реквизиты" },
];

function statusLabel(status: OnboardingDocStatus): string {
  if (status === "UPLOADED") return "Загружено";
  if (status === "VERIFIED") return "Принято";
  return "Отклонено";
}

export function OnboardingSelfRegistrationPage({ mode }: { mode: "start" | "form" | "status" }) {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [inn, setInn] = useState("");
  const [orgType, setOrgType] = useState("");
  const [phone, setPhone] = useState("");
  const [ogrn, setOgrn] = useState("");
  const [application, setApplication] = useState<OnboardingApplication | null>(null);
  const [documents, setDocuments] = useState<OnboardingDocumentItem[]>([]);
  const [uploadingType, setUploadingType] = useState<OnboardingDocType | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [generatedDocs, setGeneratedDocs] = useState<GeneratedOnboardingDocumentItem[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [packageStatus, setPackageStatus] = useState<string | null>(null);

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
      const docs = await listOnboardingDocuments(session.appId);
      setDocuments(docs);
      const generated = await listGeneratedOnboardingDocuments(session.appId);
      setGeneratedDocs(generated);
    } catch (e) {
      if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
        clearOnboardingSession();
        setError("Сессия заявки устарела, начните заново");
        return;
      }
      setError(e instanceof Error ? e.message : "Не удалось загрузить данные заявки");
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

  const onUpload = async (docType: OnboardingDocType, file?: File | null) => {
    if (!session.appId || !file) return;
    setUploadingType(docType);
    setError(null);
    try {
      await uploadOnboardingDocument(session.appId, docType, file);
      const docs = await listOnboardingDocuments(session.appId);
      setDocuments(docs);
      const generated = await listGeneratedOnboardingDocuments(session.appId);
      setGeneratedDocs(generated);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось загрузить документ");
    } finally {
      setUploadingType(null);
    }
  };

  const latestForType = (docType: OnboardingDocType): OnboardingDocumentItem | undefined =>
    documents.find((item) => item.doc_type === docType);

  const docKindLabel = (kind: string) => {
    if (kind === "OFFER") return "Оферта";
    if (kind === "SERVICE_AGREEMENT") return "Договор услуг";
    if (kind === "DPA") return "DPA / 152-ФЗ";
    return kind;
  };


  const toggleDocSelection = (id: string) => {
    setSelectedDocIds((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id].slice(0, 50)));
  };

  const downloadPackage = async () => {
    if (selectedDocIds.length === 0) {
      setError("Выберите документы для выгрузки");
      return;
    }
    setBusy(true);
    setError(null);
    setPackageStatus("CREATING");
    try {
      const created = await createDocumentsPackage(selectedDocIds);
      let attempts = 0;
      while (attempts < 12) {
        const status = await getDocumentsPackageStatus(created.package_id);
        setPackageStatus(status.status);
        if (status.status === "READY") {
          await downloadDocumentsPackage(created.package_id);
          setPackageStatus("READY");
          break;
        }
        if (status.status === "FAILED") {
          throw new Error("Не удалось собрать пакет");
        }
        attempts += 1;
        const delayMs = Math.min(5000, 2000 + attempts * 300);
        await new Promise((resolve) => setTimeout(resolve, delayMs));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось скачать пакет");
      setPackageStatus("FAILED");
    } finally {
      setBusy(false);
    }
  };

  const generateDocs = async () => {
    if (!session.appId) return;
    setBusy(true);
    setError(null);
    try {
      const items = await generateOnboardingDocuments(session.appId);
      setGeneratedDocs(items);
    } catch (e) {
      if (e instanceof ApiError && e.status === 400 && (e.details as { reason_code?: string } | undefined)?.reason_code === "feature_disabled_in_prod") {
        setError("Документы будут доступны после проверки/включения подписи");
        return;
      }
      setError(e instanceof Error ? e.message : "Не удалось сформировать документы");
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
      <main style={{ maxWidth: 760, margin: "40px auto", padding: 16 }}>
        <h1>Анкета заявки</h1>
        <p>Application ID: {session.appId ?? "—"}</p>
        <label>Название компании<input value={companyName} onChange={(e) => setCompanyName(e.target.value)} /></label>
        <label>ИНН<input value={inn} onChange={(e) => setInn(e.target.value)} /></label>
        <label>Орг. форма<input value={orgType} onChange={(e) => setOrgType(e.target.value)} /></label>
        <label>Телефон<input value={phone} onChange={(e) => setPhone(e.target.value)} /></label>
        <label>ОГРН (опц.)<input value={ogrn} onChange={(e) => setOgrn(e.target.value)} /></label>
        <section style={{ marginTop: 20 }}>
          <h2>Документы</h2>
          {REQUIRED_DOC_TYPES.map((doc) => {
            const item = latestForType(doc.type);
            return (
              <div key={doc.type} style={{ display: "grid", gridTemplateColumns: "1fr auto auto", gap: 12, alignItems: "center", marginBottom: 8 }}>
                <div>
                  <div>{doc.label}</div>
                  <div style={{ color: "#666", fontSize: 13 }}>
                    {item ? `${statusLabel(item.status)}${item.status === "REJECTED" && item.rejection_reason ? `: ${item.rejection_reason}` : ""}` : "Не загружено"}
                  </div>
                </div>
                {item ? (
                  <button type="button" onClick={() => void downloadOnboardingDocument(item.id, item.filename)}>
                    Скачать
                  </button>
                ) : null}
                <label>
                  <span style={{ marginRight: 8 }}>{uploadingType === doc.type ? "Загрузка..." : "Загрузить"}</span>
                  <input
                    type="file"
                    style={{ display: "inline-block" }}
                    onChange={(e) => void onUpload(doc.type, e.target.files?.[0])}
                    disabled={uploadingType === doc.type}
                  />
                </label>
              </div>
            );
          })}
        </section>
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
      <section style={{ marginTop: 20 }}>
        <h2>Документы на подпись</h2>
        <button type="button" disabled={busy} onClick={() => void generateDocs()}>
          {busy ? "Формируем..." : "Сформировать документы"}
        </button>
        <div style={{ marginTop: 12, display: "grid", gap: 8 }}>
          {generatedDocs.map((item) => (
            <div key={item.id} style={{ display: "flex", gap: 12, alignItems: "center" }}>
              <input type="checkbox" checked={selectedDocIds.includes(item.id)} onChange={() => toggleDocSelection(item.id)} />
              <span>{docKindLabel(item.doc_kind)} v{item.version}</span>
              <span style={{ color: "#666" }}>{item.status}</span>
              <button type="button" onClick={() => void downloadGeneratedOnboardingDocument(item.id, item.filename)}>
                Скачать
              </button>
            </div>
          ))}
          {generatedDocs.length === 0 ? <span style={{ color: "#666" }}>Документы ещё не сформированы</span> : null}
        </div>
        <div style={{ marginTop: 12, display: "flex", gap: 8, alignItems: "center" }}>
          <button type="button" disabled={busy || selectedDocIds.length === 0} onClick={() => void downloadPackage()}>
            Скачать пакет
          </button>
          {packageStatus === "CREATING" ? <span style={{ color: "#666" }}>Сборка пакета…</span> : null}
          {packageStatus === "READY" ? <span style={{ color: "green" }}>Пакет готов</span> : null}
        </div>
      </section>
      {error ? <p>{error}</p> : null}
    </main>
  );
}
