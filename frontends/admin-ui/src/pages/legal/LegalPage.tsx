import { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { useLegalGate } from "../../auth/LegalGateContext";
import {
  createLegalDocument,
  listLegalAcceptances,
  listLegalDocuments,
  publishLegalDocument,
  updateLegalDocument,
} from "../../api/legal";
import type { LegalAcceptance, LegalDocument } from "../../api/legal";

const emptyForm = {
  code: "",
  version: "",
  title: "",
  locale: "ru",
  effective_from: "",
  content_type: "MARKDOWN",
  content: "",
};

const formatDate = (value?: string | null) => {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("ru-RU");
  } catch {
    return value;
  }
};

const toInputDateTime = (value?: string | null) => {
  if (!value) return "";
  const date = new Date(value);
  return date.toISOString().slice(0, 16);
};

export default function LegalPage() {
  const { accessToken } = useAuth();
  const { required, isBlocked, isLoading: legalLoading, accept, refresh } = useLegalGate();
  const [documents, setDocuments] = useState<LegalDocument[]>([]);
  const [acceptances, setAcceptances] = useState<LegalAcceptance[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [filters, setFilters] = useState({ code: "", locale: "", status: "" });
  const [acceptanceFilters, setAcceptanceFilters] = useState({ subject_id: "", document_code: "" });
  const [isSaving, setIsSaving] = useState(false);

  const canUseApi = Boolean(accessToken) && !isBlocked;

  const loadDocuments = useCallback(async () => {
    if (!accessToken) return;
    const params: Record<string, string> = {};
    if (filters.code) params.code = filters.code;
    if (filters.locale) params.locale = filters.locale;
    if (filters.status) params.status = filters.status;
    const data = await listLegalDocuments(accessToken, params);
    setDocuments(data);
  }, [accessToken, filters.code, filters.locale, filters.status]);

  const loadAcceptances = useCallback(async () => {
    if (!accessToken) return;
    const params: Record<string, string> = {};
    if (acceptanceFilters.subject_id) params.subject_id = acceptanceFilters.subject_id;
    if (acceptanceFilters.document_code) params.document_code = acceptanceFilters.document_code;
    const data = await listLegalAcceptances(accessToken, params);
    setAcceptances(data);
  }, [acceptanceFilters.document_code, acceptanceFilters.subject_id, accessToken]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!canUseApi) return;
    void loadDocuments();
    void loadAcceptances();
  }, [canUseApi, loadAcceptances, loadDocuments]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!accessToken) return;
    setIsSaving(true);
    try {
      if (editingId) {
        await updateLegalDocument(accessToken, editingId, {
          title: form.title,
          locale: form.locale,
          effective_from: form.effective_from ? new Date(form.effective_from).toISOString() : form.effective_from,
          content_type: form.content_type,
          content: form.content,
        });
      } else {
        await createLegalDocument(accessToken, {
          ...form,
          effective_from: form.effective_from ? new Date(form.effective_from).toISOString() : form.effective_from,
        });
      }
      setForm(emptyForm);
      setEditingId(null);
      await loadDocuments();
    } finally {
      setIsSaving(false);
    }
  };

  const handleEdit = (doc: LegalDocument) => {
    setEditingId(doc.id);
    setForm({
      code: doc.code,
      version: doc.version,
      title: doc.title,
      locale: doc.locale,
      effective_from: toInputDateTime(doc.effective_from),
      content_type: doc.content_type,
      content: doc.content,
    });
  };

  const handlePublish = async (id: string) => {
    if (!accessToken) return;
    await publishLegalDocument(accessToken, id);
    await loadDocuments();
  };

  const requiredItems = useMemo(() => required ?? [], [required]);

  return (
    <div className="neft-container">
      <div className="card">
        <h1>Legal Documents</h1>

      <section className="legal-section">
        <h2>Acceptance Gate</h2>
        {isBlocked ? (
          <p className="muted">Для продолжения работы необходимо принять обязательные документы.</p>
        ) : (
          <p className="muted">Все обязательные документы приняты.</p>
        )}
        {legalLoading ? <div className="muted">Загружаем статус...</div> : null}
        <div className="legal-required-list">
          {requiredItems.map((item) => (
            <div key={`${item.code}-${item.required_version}-${item.locale}`} className="legal-required-item">
              <div>
                <strong>{item.title}</strong>
                <div className="muted">{item.code}</div>
                <div className="muted">Версия {item.required_version}</div>
                <div className="muted">Вступает {formatDate(item.effective_from)}</div>
              </div>
              <div>
                <label className="checkbox">
                  <input type="checkbox" readOnly checked={item.accepted} />
                  <span>{item.accepted ? `Принято ${formatDate(item.accepted_at)}` : "Не принято"}</span>
                </label>
                {!item.accepted ? (
                  <button
                    className="neft-btn-primary"
                    type="button"
                    onClick={() => accept(item.code, item.required_version, item.locale)}
                  >
                    Принять
                  </button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="legal-section">
        <h2>Documents Registry</h2>
        {isBlocked ? (
          <p className="muted">Примите документы, чтобы управлять реестром.</p>
        ) : (
          <>
            <form className="legal-form" onSubmit={handleSubmit}>
              <div className="legal-form__row">
                <label>
                  Код
                  <input
                    className="neft-input"
                    value={form.code}
                    onChange={(event) => setForm({ ...form, code: event.target.value })}
                    required
                    disabled={Boolean(editingId)}
                  />
                </label>
                <label>
                  Версия
                  <input
                    className="neft-input"
                    value={form.version}
                    onChange={(event) => setForm({ ...form, version: event.target.value })}
                    required
                    disabled={Boolean(editingId)}
                  />
                </label>
                <label>
                  Локаль
                  <input
                    className="neft-input"
                    value={form.locale}
                    onChange={(event) => setForm({ ...form, locale: event.target.value })}
                    required
                  />
                </label>
              </div>
              <label>
                Заголовок
                <input
                  className="neft-input"
                  value={form.title}
                  onChange={(event) => setForm({ ...form, title: event.target.value })}
                  required
                />
              </label>
              <div className="legal-form__row">
                <label>
                  Effective from
                  <input
                    className="neft-input"
                    type="datetime-local"
                    value={form.effective_from}
                    onChange={(event) => setForm({ ...form, effective_from: event.target.value })}
                    required
                  />
                </label>
                <label>
                  Content type
                  <select
                    className="neft-input"
                    value={form.content_type}
                    onChange={(event) => setForm({ ...form, content_type: event.target.value })}
                  >
                    <option value="MARKDOWN">MARKDOWN</option>
                    <option value="HTML">HTML</option>
                    <option value="PLAIN">PLAIN</option>
                  </select>
                </label>
              </div>
              <label>
                Контент
                <textarea
                  className="neft-input"
                  rows={6}
                  value={form.content}
                  onChange={(event) => setForm({ ...form, content: event.target.value })}
                  required
                />
              </label>
              <button className="neft-btn-primary" type="submit" disabled={isSaving}>
                {editingId ? "Обновить" : "Создать"}
              </button>
            </form>

            <div className="legal-filters">
              <input
                className="neft-input"
                placeholder="Код"
                value={filters.code}
                onChange={(event) => setFilters({ ...filters, code: event.target.value })}
              />
              <input
                className="neft-input"
                placeholder="Локаль"
                value={filters.locale}
                onChange={(event) => setFilters({ ...filters, locale: event.target.value })}
              />
              <input
                className="neft-input"
                placeholder="Статус"
                value={filters.status}
                onChange={(event) => setFilters({ ...filters, status: event.target.value })}
              />
              <button className="neft-btn-secondary" type="button" onClick={loadDocuments}>
                Фильтр
              </button>
            </div>

            <div className="legal-table">
              {documents.map((doc) => (
                <div key={doc.id} className="legal-table__row">
                  <div>
                    <strong>{doc.code}</strong> v{doc.version} ({doc.locale})
                    <div className="muted">{doc.title}</div>
                    <div className="muted">Status: {doc.status}</div>
                  </div>
                  <div className="legal-table__actions">
                    {doc.status === "DRAFT" ? (
                      <button className="ghost neft-btn-secondary" type="button" onClick={() => handlePublish(doc.id)}>
                        Publish
                      </button>
                    ) : null}
                    {doc.status === "DRAFT" ? (
                      <button className="ghost neft-btn-secondary" type="button" onClick={() => handleEdit(doc)}>
                        Edit
                      </button>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </section>

      <section className="legal-section">
        <h2>Acceptances</h2>
        {isBlocked ? (
          <p className="muted">Примите документы, чтобы просматривать акцепты.</p>
        ) : (
          <>
            <div className="legal-filters">
              <input
                className="neft-input"
                placeholder="Subject ID"
                value={acceptanceFilters.subject_id}
                onChange={(event) => setAcceptanceFilters({ ...acceptanceFilters, subject_id: event.target.value })}
              />
              <input
                className="neft-input"
                placeholder="Document code"
                value={acceptanceFilters.document_code}
                onChange={(event) => setAcceptanceFilters({ ...acceptanceFilters, document_code: event.target.value })}
              />
              <button className="neft-btn-secondary" type="button" onClick={loadAcceptances}>
                Искать
              </button>
            </div>
            <div className="legal-table">
              {acceptances.map((item) => (
                <div key={item.id} className="legal-table__row">
                  <div>
                    <strong>{item.subject_type}</strong> {item.subject_id}
                    <div className="muted">
                      {item.document_code} v{item.document_version} ({item.document_locale})
                    </div>
                    <div className="muted">{formatDate(item.accepted_at)}</div>
                  </div>
                  <div className="muted">{item.ip ?? "—"}</div>
                </div>
              ))}
            </div>
          </>
        )}
      </section>
      </div>
    </div>
  );
}
