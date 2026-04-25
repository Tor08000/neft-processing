import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { useAdmin } from "../../admin/AdminContext";
import {
  createLegalDocument,
  listLegalAcceptances,
  listLegalDocuments,
  publishLegalDocument,
  updateLegalDocument,
} from "../../api/legal";
import type { LegalAcceptance, LegalDocument } from "../../api/legal";
import { EmptyState } from "../../components/common/EmptyState";
import { ErrorState } from "../../components/common/ErrorState";
import { describeRuntimeError, type RuntimeErrorMeta } from "../../api/runtimeError";
import { Loader } from "../../components/Loader/Loader";

const emptyForm = {
  code: "",
  version: "",
  title: "",
  locale: "ru",
  effective_from: "",
  content_type: "MARKDOWN",
  content: "",
};

const EMPTY_VALUE = "-";

const formatDate = (value?: string | null) => {
  if (!value) return EMPTY_VALUE;
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
  const { profile } = useAdmin();
  const [documents, setDocuments] = useState<LegalDocument[]>([]);
  const [acceptances, setAcceptances] = useState<LegalAcceptance[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [filters, setFilters] = useState({ code: "", locale: "", status: "" });
  const [acceptanceFilters, setAcceptanceFilters] = useState({ subject_id: "", document_code: "" });
  const [isSaving, setIsSaving] = useState(false);
  const [isDocumentsLoading, setIsDocumentsLoading] = useState(false);
  const [isAcceptancesLoading, setIsAcceptancesLoading] = useState(false);
  const [documentsError, setDocumentsError] = useState<RuntimeErrorMeta | null>(null);
  const [acceptancesError, setAcceptancesError] = useState<RuntimeErrorMeta | null>(null);

  const canRead = Boolean(profile?.permissions.legal?.read);
  const canOperate = Boolean(profile?.permissions.legal?.operate) && !profile?.read_only;
  const canApprove = Boolean(profile?.permissions.legal?.approve) && !profile?.read_only;
  const canUseApi = Boolean(accessToken) && canRead;
  const documentsFiltersActive = Boolean(filters.code || filters.locale || filters.status);
  const acceptanceFiltersActive = Boolean(acceptanceFilters.subject_id || acceptanceFilters.document_code);

  const resetDocumentFilters = () => setFilters({ code: "", locale: "", status: "" });
  const resetAcceptanceFilters = () => setAcceptanceFilters({ subject_id: "", document_code: "" });

  const loadDocuments = useCallback(async () => {
    if (!accessToken) return;
    setIsDocumentsLoading(true);
    setDocumentsError(null);
    const params: Record<string, string> = {};
    if (filters.code) params.code = filters.code;
    if (filters.locale) params.locale = filters.locale;
    if (filters.status) params.status = filters.status;
    try {
      const data = await listLegalDocuments(accessToken, params);
      setDocuments(data);
    } catch (error) {
      setDocumentsError(describeRuntimeError(error, "Failed to load legal documents registry."));
    } finally {
      setIsDocumentsLoading(false);
    }
  }, [accessToken, filters.code, filters.locale, filters.status]);

  const loadAcceptances = useCallback(async () => {
    if (!accessToken) return;
    setIsAcceptancesLoading(true);
    setAcceptancesError(null);
    const params: Record<string, string> = {};
    if (acceptanceFilters.subject_id) params.subject_id = acceptanceFilters.subject_id;
    if (acceptanceFilters.document_code) params.document_code = acceptanceFilters.document_code;
    try {
      const data = await listLegalAcceptances(accessToken, params);
      setAcceptances(data);
    } catch (error) {
      setAcceptancesError(describeRuntimeError(error, "Failed to load legal acceptances."));
    } finally {
      setIsAcceptancesLoading(false);
    }
  }, [acceptanceFilters.document_code, acceptanceFilters.subject_id, accessToken]);

  useEffect(() => {
    if (!canUseApi) return;
    void loadDocuments();
    void loadAcceptances();
  }, [canUseApi, loadAcceptances, loadDocuments]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!accessToken) return;
    setIsSaving(true);
    setDocumentsError(null);
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
    } catch (error) {
      setDocumentsError(describeRuntimeError(error, "Failed to save legal document."));
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
    setDocumentsError(null);
    try {
      await publishLegalDocument(accessToken, id);
      await loadDocuments();
    } catch (error) {
      setDocumentsError(describeRuntimeError(error, "Failed to publish legal document."));
    }
  };

  return (
    <div className="stack">
      <div className="page-header">
        <div>
          <h1>Legal documents</h1>
          <p className="muted">Canonical operator registry for legal documents, acceptances, and partner review.</p>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <Link to="/legal/documents">Documents</Link>
          <Link to="/legal/partners">Partners</Link>
          {!canOperate ? <span className="muted">Read-only mode: create and edit actions are disabled.</span> : null}
        </div>
      </div>

      <section className="legal-section">
        <h2>Documents Registry</h2>
        {!canUseApi ? (
          <EmptyState
            title="Legal access is limited"
            description="The current admin profile cannot open the legal documents owner surface."
            hint="Switch to an admin account with legal read permissions."
          />
        ) : (
          <>
            {canOperate ? (
              <form className="legal-form" onSubmit={handleSubmit}>
                <div className="legal-form__row">
                  <label>
                    Code
                    <input
                      className="neft-input"
                      value={form.code}
                      onChange={(event) => setForm({ ...form, code: event.target.value })}
                      required
                      disabled={Boolean(editingId)}
                    />
                  </label>
                  <label>
                    Version
                    <input
                      className="neft-input"
                      value={form.version}
                      onChange={(event) => setForm({ ...form, version: event.target.value })}
                      required
                      disabled={Boolean(editingId)}
                    />
                  </label>
                  <label>
                    Locale
                    <input
                      className="neft-input"
                      value={form.locale}
                      onChange={(event) => setForm({ ...form, locale: event.target.value })}
                      required
                    />
                  </label>
                </div>
                <label>
                  Title
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
                  Content
                  <textarea
                    className="neft-input"
                    rows={6}
                    value={form.content}
                    onChange={(event) => setForm({ ...form, content: event.target.value })}
                    required
                  />
                </label>
                <button className="neft-btn-primary" type="submit" disabled={isSaving}>
                  {editingId ? "Update" : "Create"}
                </button>
              </form>
            ) : null}

            {isDocumentsLoading && !documents.length && !documentsError ? <Loader label="Loading legal documents registry" /> : null}

            {documentsError ? (
              <ErrorState
                title="Failed to load legal documents registry"
                description={documentsError.description}
                actionLabel="Retry"
                onAction={() => void loadDocuments()}
                details={documentsError.details}
                requestId={documentsError.requestId}
                correlationId={documentsError.correlationId}
              />
            ) : null}

            <div className="legal-filters">
              <input
                className="neft-input"
                placeholder="Code"
                value={filters.code}
                onChange={(event) => setFilters({ ...filters, code: event.target.value })}
              />
              <input
                className="neft-input"
                placeholder="Locale"
                value={filters.locale}
                onChange={(event) => setFilters({ ...filters, locale: event.target.value })}
              />
              <input
                className="neft-input"
                placeholder="Status"
                value={filters.status}
                onChange={(event) => setFilters({ ...filters, status: event.target.value })}
              />
              <button className="neft-btn-secondary" type="button" onClick={() => void loadDocuments()} disabled={isDocumentsLoading}>
                {isDocumentsLoading ? "Refreshing..." : "Apply filters"}
              </button>
              {documentsFiltersActive ? (
                <button className="ghost neft-btn-secondary" type="button" onClick={resetDocumentFilters}>
                  Reset
                </button>
              ) : null}
            </div>

            {!documentsError && !isDocumentsLoading ? (
              documents.length ? (
                <div className="legal-table">
                  {documents.map((doc) => (
                    <div key={doc.id} className="legal-table__row">
                      <div>
                        <strong>{doc.code}</strong> v{doc.version} ({doc.locale})
                        <div className="muted">{doc.title}</div>
                        <div className="muted">Status: {doc.status}</div>
                      </div>
                      <div className="legal-table__actions">
                        {doc.status === "DRAFT" && canApprove ? (
                          <button className="ghost neft-btn-secondary" type="button" onClick={() => void handlePublish(doc.id)}>
                            Publish
                          </button>
                        ) : null}
                        {doc.status === "DRAFT" && canOperate ? (
                          <button className="ghost neft-btn-secondary" type="button" onClick={() => handleEdit(doc)}>
                            Edit
                          </button>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState
                  title={documentsFiltersActive ? "No legal documents match the current filters" : "Legal registry is ready for the first document"}
                  description={
                    documentsFiltersActive
                      ? "Broaden the current filters or reset the registry search."
                      : "Create the first legal document or wait until the legal registry starts receiving canonical entries."
                  }
                  hint={
                    documentsFiltersActive
                      ? "Filtered-empty state is scoped only to the current search contour."
                      : "The owner route is healthy but has not received any legal documents yet."
                  }
                  primaryAction={documentsFiltersActive ? { label: "Reset filters", onClick: resetDocumentFilters } : undefined}
                />
              )
            ) : null}
          </>
        )}
      </section>

      <section className="legal-section">
        <h2>Acceptances</h2>
        {!canUseApi ? (
          <EmptyState
            title="Legal access is limited"
            description="The current admin profile cannot access legal acceptances."
          />
        ) : (
          <>
            {isAcceptancesLoading && !acceptances.length && !acceptancesError ? <Loader label="Loading legal acceptances" /> : null}
            {acceptancesError ? (
              <ErrorState
                title="Failed to load legal acceptances"
                description={acceptancesError.description}
                actionLabel="Retry"
                onAction={() => void loadAcceptances()}
                details={acceptancesError.details}
                requestId={acceptancesError.requestId}
                correlationId={acceptancesError.correlationId}
              />
            ) : null}
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
              <button className="neft-btn-secondary" type="button" onClick={() => void loadAcceptances()} disabled={isAcceptancesLoading}>
                {isAcceptancesLoading ? "Searching..." : "Search"}
              </button>
              {acceptanceFiltersActive ? (
                <button className="ghost neft-btn-secondary" type="button" onClick={resetAcceptanceFilters}>
                  Reset
                </button>
              ) : null}
            </div>
            {!acceptancesError && !isAcceptancesLoading ? (
              acceptances.length ? (
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
                      <div className="muted">{item.ip ?? EMPTY_VALUE}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState
                  title={acceptanceFiltersActive ? "No acceptances match the current search" : "No legal acceptances yet"}
                  description={
                    acceptanceFiltersActive
                      ? "Broaden the current filters or reset the acceptance search."
                      : "The acceptance registry is healthy but has not received any legal acknowledgements yet."
                  }
                  hint={
                    acceptanceFiltersActive
                      ? "Filtered-empty state is scoped only to the current acceptance search."
                      : "Acceptances will appear here after the first legal acknowledgement is recorded."
                  }
                  primaryAction={acceptanceFiltersActive ? { label: "Reset filters", onClick: resetAcceptanceFilters } : undefined}
                />
              )
            ) : null}
          </>
        )}
      </section>
    </div>
  );
}
