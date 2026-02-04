import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Wrench } from "../components/icons";
import {
  activateCatalogItem,
  createCatalogItem,
  disableCatalogItem,
  fetchCatalogItems,
  previewCatalogImport,
  updateCatalogItem,
  applyCatalogImport,
} from "../api/catalog";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { EmptyState } from "../components/EmptyState";
import { ForbiddenState } from "../components/states";
import { StatusBadge } from "../components/StatusBadge";
import { formatDateTime, formatNumber } from "../utils/format";
import { parseCatalogCsv } from "../utils/csv";
import { canManageServices, canReadServices } from "../utils/roles";
import type { CatalogItem, CatalogItemInput, CatalogItemKind, CatalogItemStatus, CatalogImportPreview } from "../types/marketplace";
import { useI18n } from "../i18n";
import { PartnerErrorState } from "../components/PartnerErrorState";
import { demoCatalogItems } from "../demo/partnerDemoData";
import { isDemoPartner } from "@shared/demo/demo";

type ApiErrorState = {
  message: string;
};

type CatalogFormState = {
  title: string;
  description: string;
  kind: CatalogItemKind;
  category: string;
  baseUom: string;
  status: CatalogItemStatus;
};

type ImportMode = "create" | "upsert";

const defaultFormState: CatalogFormState = {
  title: "",
  description: "",
  kind: "SERVICE",
  category: "",
  baseUom: "",
  status: "DRAFT",
};

const localStorageKey = "partner-services-catalog-filters";

const normalizeError = (error: unknown, fallback: string): ApiErrorState => {
  if (error instanceof ApiError) {
    return { message: fallback };
  }
  if (error instanceof Error) {
    return { message: fallback };
  }
  return { message: fallback };
};

const formatErrorDescription = (error: ApiErrorState): string => {
  return error.message;
};

const resolveCatalogTone = (status: CatalogItemStatus): "success" | "pending" | "error" | "neutral" => {
  switch (status) {
    case "ACTIVE":
      return "success";
    case "DISABLED":
      return "pending";
    case "ARCHIVED":
      return "error";
    case "DRAFT":
    default:
      return "neutral";
  }
};

const buildCatalogPayload = (form: CatalogFormState): CatalogItemInput => ({
  title: form.title.trim(),
  description: form.description.trim() || null,
  kind: form.kind,
  category: form.category.trim() || null,
  baseUom: form.baseUom.trim(),
  status: form.status,
});

const buildCatalogForm = (item?: CatalogItem | null): CatalogFormState => ({
  title: item?.title ?? "",
  description: item?.description ?? "",
  kind: item?.kind ?? "SERVICE",
  category: item?.category ?? "",
  baseUom: item?.baseUom ?? "",
  status: item?.status ?? "DRAFT",
});

const resolveSummaryValue = (value: number | undefined | null): string => (value === null || value === undefined ? "—" : String(value));

const getSummary = (preview: CatalogImportPreview | null, fallbackRows: number, fallbackErrors: number) => {
  const summary = preview?.summary;
  return {
    rowsParsed: resolveSummaryValue(summary?.rowsParsed ?? fallbackRows),
    willCreate: resolveSummaryValue(summary?.willCreate),
    willUpdate: resolveSummaryValue(summary?.willUpdate),
    errorsCount: resolveSummaryValue(summary?.errorsCount ?? fallbackErrors),
  };
};

export function ServicesCatalogPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const canRead = canReadServices(user?.roles);
  const canManage = canManageServices(user?.roles);
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const [filters, setFilters] = useState({
    q: "",
    kind: "ALL",
    status: "ALL",
    category: "",
  });
  const [error, setError] = useState<unknown>(null);
  const [isDemoFallback, setIsDemoFallback] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<CatalogItem | null>(null);
  const [formState, setFormState] = useState<CatalogFormState>(defaultFormState);
  const [formError, setFormError] = useState<ApiErrorState | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [actionCorrelation, setActionCorrelation] = useState<string | null>(null);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importMode, setImportMode] = useState<ImportMode>("create");
  const [importPreview, setImportPreview] = useState<CatalogImportPreview | null>(null);
  const [importParsingRows, setImportParsingRows] = useState<Record<string, string>[]>([]);
  const [importParsingErrors, setImportParsingErrors] = useState<string[]>([]);
  const [importLoading, setImportLoading] = useState(false);
  const [importApplyLoading, setImportApplyLoading] = useState(false);
  const [importApplyResult, setImportApplyResult] = useState<{
    created: number;
    updated: number;
    skipped: number;
  } | null>(null);
  const [importError, setImportError] = useState<ApiErrorState | null>(null);
  const hasFilters =
    Boolean(filters.q) || Boolean(filters.category) || filters.kind !== "ALL" || filters.status !== "ALL";

  useEffect(() => {
    const stored = window.localStorage.getItem(localStorageKey);
    if (stored) {
      try {
        const parsed = JSON.parse(stored) as typeof filters;
        setFilters((prev) => ({ ...prev, ...parsed }));
      } catch {
        window.localStorage.removeItem(localStorageKey);
      }
    }
  }, []);

  useEffect(() => {
    window.localStorage.setItem(localStorageKey, JSON.stringify(filters));
  }, [filters]);

  const fetchItems = async () => {
    if (!user) return;
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetchCatalogItems(user.token, {
        q: filters.q || undefined,
        kind: filters.kind !== "ALL" ? filters.kind : undefined,
        status: filters.status !== "ALL" ? filters.status : undefined,
        category: filters.category || undefined,
        limit: String(pageSize),
        offset: String((page - 1) * pageSize),
      });
      setItems(response.items ?? []);
      setTotal(response.total ?? 0);
      setIsDemoFallback(false);
    } catch (err) {
      if (err instanceof ApiError && isDemoPartner(user.email ?? null) && (err.status === 403 || err.status === 404)) {
        setItems(demoCatalogItems);
        setTotal(demoCatalogItems.length);
        setIsDemoFallback(true);
        setError(null);
        return;
      }
      setError(err);
    } finally {
      setIsLoading(false);
    }
  };

  const resetFilters = () => {
    setFilters({ q: "", kind: "ALL", status: "ALL", category: "" });
    setPage(1);
  };

  useEffect(() => {
    if (!user || !canRead) return;
    fetchItems();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, canRead, page, pageSize, filters]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const openCreateModal = () => {
    setEditingItem(null);
    setFormState(defaultFormState);
    setFormError(null);
    setActionNotice(null);
    setActionCorrelation(null);
    setModalOpen(true);
  };

  const openEditModal = (item: CatalogItem) => {
    setEditingItem(item);
    setFormState(buildCatalogForm(item));
    setFormError(null);
    setActionNotice(null);
    setActionCorrelation(null);
    setModalOpen(true);
  };

  const handleSave = async (activate = false) => {
    if (!user) return;
    if (!formState.title.trim() || !formState.baseUom.trim()) {
      setFormError({ message: t("servicesCatalogPage.errors.requiredFields") });
      return;
    }
    setFormError(null);
    setActionNotice(null);
    setActionCorrelation(null);
    try {
      const payload = buildCatalogPayload({ ...formState, status: activate ? "ACTIVE" : formState.status });
      if (editingItem) {
        const result = await updateCatalogItem(user.token, editingItem.id, payload);
        setActionNotice(t("servicesCatalogPage.notifications.saved"));
        setActionCorrelation(result.correlationId ?? null);
        setItems((prev) => prev.map((item) => (item.id === editingItem.id ? result.data : item)));
      } else {
        const result = await createCatalogItem(user.token, payload);
        setActionNotice(t("servicesCatalogPage.notifications.created"));
        setActionCorrelation(result.correlationId ?? null);
        setItems((prev) => [result.data, ...prev]);
        setTotal((prev) => prev + 1);
      }
      setModalOpen(false);
    } catch (err) {
      setFormError(normalizeError(err, t("servicesCatalogPage.errors.saveFailed")));
    }
  };

  const handleToggleStatus = async (item: CatalogItem) => {
    if (!user) return;
    setActionNotice(null);
    setActionCorrelation(null);
    try {
      if (item.status === "ACTIVE") {
        const result = await disableCatalogItem(user.token, item.id);
        setItems((prev) => prev.map((entry) => (entry.id === item.id ? { ...entry, status: "DISABLED" } : entry)));
        setActionNotice(t("servicesCatalogPage.notifications.disabled"));
        setActionCorrelation(result.correlationId ?? null);
      } else {
        const result = await activateCatalogItem(user.token, item.id);
        setItems((prev) => prev.map((entry) => (entry.id === item.id ? { ...entry, status: "ACTIVE" } : entry)));
        setActionNotice(t("servicesCatalogPage.notifications.activated"));
        setActionCorrelation(result.correlationId ?? null);
      }
    } catch (err) {
      setError(normalizeError(err, t("servicesCatalogPage.errors.updateStatusFailed")));
    }
  };

  const handlePreviewImport = async () => {
    if (!user || !importFile) {
      setImportError({ message: t("servicesCatalogPage.import.errors.selectCsv") });
      return;
    }
    setImportError(null);
    setImportPreview(null);
    setImportApplyResult(null);
    setImportParsingErrors([]);
    setImportParsingRows([]);
    setImportLoading(true);
    try {
      const text = await importFile.text();
      const parsed = parseCatalogCsv(text);
      if (parsed.errors.length) {
        setImportParsingErrors(parsed.errors.map((row) => t("servicesCatalogPage.import.errors.row", { row: row.row, message: row.message })));
        setImportParsingRows(parsed.rows);
        return;
      }
      setImportParsingRows(parsed.rows);
      const preview = await previewCatalogImport(user.token, importFile, importMode);
      setImportPreview({
        headers: preview.headers ?? parsed.headers,
        rows: preview.rows ?? parsed.rows,
        errors: preview.errors ?? [],
        summary: preview.summary ?? null,
      });
    } catch (err) {
      setImportError(normalizeError(err, t("servicesCatalogPage.import.errors.previewFailed")));
    } finally {
      setImportLoading(false);
    }
  };

  const handleApplyImport = async () => {
    if (!user || !importFile) return;
    setImportApplyLoading(true);
    setImportError(null);
    try {
      const result = await applyCatalogImport(user.token, importFile, importMode);
      setImportApplyResult({
        created: result.createdCount ?? result.created ?? 0,
        updated: result.updatedCount ?? result.updated ?? 0,
        skipped: result.skippedCount ?? result.failed ?? 0,
      });
      setImportPreview(null);
    } catch (err) {
      setImportError(normalizeError(err, t("servicesCatalogPage.import.errors.applyFailed")));
    } finally {
      setImportApplyLoading(false);
    }
  };

  const previewSummary = useMemo(() => {
    if (!importPreview) {
      return getSummary(null, importParsingRows.length, importParsingErrors.length);
    }
    return getSummary(importPreview, importPreview.rows.length, importPreview.errors.length);
  }, [importPreview, importParsingRows, importParsingErrors]);

  if (!canRead) {
    return <ForbiddenState />;
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <div>
            <h2>{t("servicesCatalogPage.title")}</h2>
            <div className="muted">{t("servicesCatalogPage.subtitle")}</div>
          </div>
          {canManage ? (
            <button type="button" className="primary" onClick={openCreateModal}>
              {t("actions.create")}
            </button>
          ) : null}
        </div>
        <div className="filters">
          <label className="filter">
            {t("servicesCatalogPage.filters.search")}
            <input
              type="search"
              placeholder={t("servicesCatalogPage.filters.searchPlaceholder")}
              value={filters.q}
              onChange={(event) => {
                setFilters((prev) => ({ ...prev, q: event.target.value }));
                setPage(1);
              }}
            />
          </label>
          <label className="filter">
            {t("servicesCatalogPage.filters.kind")}
            <select
              value={filters.kind}
              onChange={(event) => {
                setFilters((prev) => ({ ...prev, kind: event.target.value }));
                setPage(1);
              }}
            >
              <option value="ALL">{t("common.all")}</option>
              <option value="SERVICE">{t("servicesCatalogPage.filters.kindOptions.service")}</option>
              <option value="PRODUCT">{t("servicesCatalogPage.filters.kindOptions.product")}</option>
            </select>
          </label>
          <label className="filter">
            {t("servicesCatalogPage.filters.status")}
            <select
              value={filters.status}
              onChange={(event) => {
                setFilters((prev) => ({ ...prev, status: event.target.value }));
                setPage(1);
              }}
            >
              <option value="ALL">{t("common.all")}</option>
              <option value="DRAFT">{t("servicesCatalogPage.filters.statusOptions.draft")}</option>
              <option value="ACTIVE">{t("servicesCatalogPage.filters.statusOptions.active")}</option>
              <option value="DISABLED">{t("servicesCatalogPage.filters.statusOptions.disabled")}</option>
              <option value="ARCHIVED">{t("servicesCatalogPage.filters.statusOptions.archived")}</option>
            </select>
          </label>
          <label className="filter">
            {t("servicesCatalogPage.filters.category")}
            <input
              type="text"
              placeholder={t("servicesCatalogPage.filters.categoryPlaceholder")}
              value={filters.category}
              onChange={(event) => {
                setFilters((prev) => ({ ...prev, category: event.target.value }));
                setPage(1);
              }}
            />
          </label>
        </div>
        {actionNotice ? (
          <div className="notice">
            <div>{actionNotice}</div>
          </div>
        ) : null}
        {isDemoFallback ? (
          <div className="notice">
            <div>В демо-режиме доступен примерный каталог услуг.</div>
          </div>
        ) : null}
        {isLoading ? (
          <div className="skeleton-stack" aria-busy="true">
            <div className="skeleton-line" />
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        ) : error ? (
          <PartnerErrorState
            error={error}
            description={t("servicesCatalogPage.errors.loadFailed")}
            action={
              <button type="button" className="secondary" onClick={fetchItems}>
                {t("errors.retry")}
              </button>
            }
          />
        ) : items.length === 0 ? (
          <EmptyState
            icon={<Wrench />}
            title={hasFilters ? t("servicesCatalogPage.empty.filteredTitle") : t("emptyStates.servicesCatalog.title")}
            description={
              hasFilters ? t("servicesCatalogPage.empty.filteredDescription") : t("emptyStates.servicesCatalog.description")
            }
            primaryAction={
              hasFilters
                ? {
                    label: t("servicesCatalogPage.actions.resetFilters"),
                    onClick: resetFilters,
                    variant: "secondary",
                  }
                : canManage
                ? {
                    label: t("actions.addService"),
                    onClick: openCreateModal,
                  }
                : undefined
            }
          />
        ) : (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>{t("servicesCatalogPage.table.title")}</th>
                  <th>{t("servicesCatalogPage.table.kind")}</th>
                  <th>{t("servicesCatalogPage.table.category")}</th>
                  <th>{t("servicesCatalogPage.table.status")}</th>
                  <th>{t("servicesCatalogPage.table.activeOffers")}</th>
                  <th>{t("servicesCatalogPage.table.updatedAt")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.title}</td>
                    <td>{item.kind}</td>
                    <td>{item.category ?? t("common.notAvailable")}</td>
                    <td>
                      <StatusBadge status={item.status} tone={resolveCatalogTone(item.status)} />
                    </td>
                    <td>{formatNumber(item.activeOffersCount ?? null)}</td>
                    <td>{formatDateTime(item.updatedAt)}</td>
                    <td>
                      <div className="stack-inline">
                        <Link to={`/services/${item.id}`} className="link-button">
                          {t("common.open")}
                        </Link>
                        {canManage ? (
                          <>
                            <button type="button" className="ghost" onClick={() => openEditModal(item)}>
                              {t("actions.edit")}
                            </button>
                            <button type="button" className="ghost" onClick={() => handleToggleStatus(item)}>
                              {item.status === "ACTIVE" ? t("servicesCatalogPage.actions.disable") : t("servicesCatalogPage.actions.activate")}
                            </button>
                          </>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="pagination">
              <button type="button" className="secondary" onClick={() => setPage((prev) => Math.max(prev - 1, 1))} disabled={page <= 1}>
                {t("common.back")}
              </button>
              <div className="muted">
                {t("servicesCatalogPage.pagination", { current: page, total: totalPages })}
              </div>
              <button
                type="button"
                className="secondary"
                onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))}
                disabled={page >= totalPages}
              >
                {t("common.next")}
              </button>
            </div>
          </>
        )}
      </section>

      <section className="card">
        <div className="section-title">
          <h3>{t("servicesCatalogPage.import.title")}</h3>
          <div className="muted">{t("servicesCatalogPage.import.subtitle")}</div>
        </div>
        {!canManage ? (
          <EmptyState
            icon={<Wrench />}
            title={t("servicesCatalogPage.import.unavailableTitle")}
            description={t("servicesCatalogPage.import.unavailableDescription")}
          />
        ) : (
          <div className="stack">
            <div className="form-grid">
              <label className="form-field">
                {t("servicesCatalogPage.import.csvFile")}
                <input
                  type="file"
                  accept=".csv,text/csv"
                  onChange={(event) => setImportFile(event.target.files?.[0] ?? null)}
                />
              </label>
              <label className="form-field">
                {t("servicesCatalogPage.import.mode")}
                <select value={importMode} onChange={(event) => setImportMode(event.target.value as ImportMode)}>
                  <option value="create">{t("servicesCatalogPage.import.modes.create")}</option>
                  <option value="upsert">{t("servicesCatalogPage.import.modes.upsert")}</option>
                </select>
              </label>
              <div className="form-grid__actions">
                <button type="button" className="secondary" onClick={handlePreviewImport} disabled={importLoading}>
                  {t("servicesCatalogPage.import.preview")}
                </button>
              </div>
            </div>
            {importError ? (
              <div className="notice error">
                {formatErrorDescription(importError)}
              </div>
            ) : null}
            {importParsingErrors.length ? (
              <div className="notice error">
                <div>{t("servicesCatalogPage.import.csvError")}</div>
                <ul>
                  {importParsingErrors.map((message) => (
                    <li key={message}>{message}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {importPreview ? (
              <div className="stack">
                <div className="notice">
                  <div className="label">{t("servicesCatalogPage.import.previewSummary")}</div>
                  <div className="grid two">
                    <div>{t("servicesCatalogPage.import.rowsParsed", { count: previewSummary.rowsParsed })}</div>
                    <div>{t("servicesCatalogPage.import.willCreate", { count: previewSummary.willCreate })}</div>
                    <div>{t("servicesCatalogPage.import.willUpdate", { count: previewSummary.willUpdate })}</div>
                    <div>{t("servicesCatalogPage.import.errorsCount", { count: previewSummary.errorsCount })}</div>
                  </div>
                </div>
                {importPreview.errors.length ? (
                  <div className="notice error">
                    <div className="label">{t("servicesCatalogPage.import.errorsTitle")}</div>
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>{t("servicesCatalogPage.import.table.row")}</th>
                          <th>{t("servicesCatalogPage.import.table.description")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {importPreview.errors.map((row) => (
                          <tr key={`${row.row}-${row.message}`}>
                            <td>{row.row}</td>
                            <td>{row.message}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
                {importPreview.rows.length ? (
                  <div>
                    <div className="label">{t("servicesCatalogPage.import.sampleTitle")}</div>
                    <table className="data-table">
                      <thead>
                        <tr>
                          {Object.keys(importPreview.rows[0]).map((header) => (
                            <th key={header}>{header}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {importPreview.rows.slice(0, 20).map((row, index) => (
                          <tr key={`${row.title ?? "row"}-${index}`}>
                            {Object.values(row).map((value, columnIndex) => (
                              <td key={`${index}-${columnIndex}`}>{value || t("common.notAvailable")}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : null}
                <div className="form-actions">
                  <button
                    type="button"
                    className="primary"
                    onClick={handleApplyImport}
                    disabled={importApplyLoading || importPreview.errors.length > 0}
                  >
                    {t("servicesCatalogPage.import.apply")}
                  </button>
                </div>
              </div>
            ) : null}
            {importApplyResult ? (
              <div className="notice">
                <div className="label">{t("servicesCatalogPage.import.resultTitle")}</div>
                <div className="grid two">
                  <div>{t("servicesCatalogPage.import.resultCreated", { count: importApplyResult.created })}</div>
                  <div>{t("servicesCatalogPage.import.resultUpdated", { count: importApplyResult.updated })}</div>
                  <div>{t("servicesCatalogPage.import.resultSkipped", { count: importApplyResult.skipped })}</div>
                </div>
                <button type="button" className="link-button" onClick={fetchItems}>
                  {t("servicesCatalogPage.import.refreshList")}
                </button>
              </div>
            ) : null}
            <div className="notice">
              <div className="label">{t("servicesCatalogPage.import.csvFormat")}</div>
              <div className="muted">{t("servicesCatalogPage.import.requiredFields")}</div>
              <pre className="code-block">
                kind,title,category,uom,description,status{"\n"}
                {t("servicesCatalogPage.import.sampleRow")}
              </pre>
            </div>
          </div>
        )}
      </section>

      {modalOpen ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <div className="card__header">
              <h3>
                {editingItem ? t("servicesCatalogPage.modal.editTitle") : t("servicesCatalogPage.modal.createTitle")}
              </h3>
              <button type="button" className="ghost" onClick={() => setModalOpen(false)}>
                {t("actions.close")}
              </button>
            </div>
            <div className="form-grid">
              <label className="form-field">
                {t("servicesCatalogPage.modal.fields.title")}
                <input
                  type="text"
                  value={formState.title}
                  onChange={(event) => setFormState((prev) => ({ ...prev, title: event.target.value }))}
                />
              </label>
              <label className="form-field">
                {t("servicesCatalogPage.modal.fields.kind")}
                <select value={formState.kind} onChange={(event) => setFormState((prev) => ({ ...prev, kind: event.target.value as CatalogItemKind }))}>
                  <option value="SERVICE">SERVICE</option>
                  <option value="PRODUCT">PRODUCT</option>
                </select>
              </label>
              <label className="form-field">
                {t("servicesCatalogPage.modal.fields.category")}
                <input
                  type="text"
                  value={formState.category}
                  onChange={(event) => setFormState((prev) => ({ ...prev, category: event.target.value }))}
                />
              </label>
              <label className="form-field">
                {t("servicesCatalogPage.modal.fields.uom")}
                <input
                  type="text"
                  placeholder={t("servicesCatalogPage.modal.fields.uomPlaceholder")}
                  value={formState.baseUom}
                  onChange={(event) => setFormState((prev) => ({ ...prev, baseUom: event.target.value }))}
                />
              </label>
              <label className="form-field form-grid__full">
                {t("servicesCatalogPage.modal.fields.description")}
                <textarea
                  className="textarea"
                  rows={3}
                  value={formState.description}
                  onChange={(event) => setFormState((prev) => ({ ...prev, description: event.target.value }))}
                />
              </label>
              <label className="form-field">
                {t("servicesCatalogPage.modal.fields.status")}
                <select
                  value={formState.status}
                  onChange={(event) => setFormState((prev) => ({ ...prev, status: event.target.value as CatalogItemStatus }))}
                >
                  <option value="DRAFT">DRAFT</option>
                  <option value="ACTIVE">ACTIVE</option>
                </select>
              </label>
            </div>
            {formError ? (
              <div className="notice error">
                {formatErrorDescription(formError)}
              </div>
            ) : null}
            <div className="form-actions">
              <button type="button" className="primary" onClick={() => handleSave(false)}>
                {t("actions.save")}
              </button>
              {canManage ? (
                <button type="button" className="secondary" onClick={() => handleSave(true)}>
                  {t("servicesCatalogPage.modal.actions.saveActivate")}
                </button>
              ) : null}
              <button type="button" className="ghost" onClick={() => setModalOpen(false)}>
                {t("actions.cancel")}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
