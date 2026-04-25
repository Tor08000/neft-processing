import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Wrench } from "../../components/icons";
import {
  activateCatalogItem,
  createCatalogItem,
  disableCatalogItem,
  fetchCatalogItems,
  previewCatalogImport,
  updateCatalogItem,
  applyCatalogImport,
} from "../../api/catalog";
import { useAuth } from "../../auth/AuthContext";
import { usePortal } from "../../auth/PortalContext";
import { EmptyState } from "../../components/EmptyState";
import { ForbiddenState } from "../../components/states";
import { StatusBadge } from "../../components/StatusBadge";
import { formatDateTime, formatNumber } from "../../utils/format";
import { parseCatalogCsv } from "../../utils/csv";
import { canManageServices, canReadServices } from "../../utils/roles";
import { resolveEffectivePartnerRoles } from "../../access/partnerWorkspace";
import type { CatalogItem, CatalogItemInput, CatalogItemKind, CatalogItemStatus, CatalogImportPreview } from "../../types/marketplace";
import { PartnerErrorState } from "../../components/PartnerErrorState";
import { ApiError } from "../../api/http";

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
const DEBUG_SERVICE_CATALOG_ERRORS = Boolean(import.meta.env.DEV && import.meta.env.VITE_PARTNER_DEBUG_ERRORS === "true");

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
const toNum = (value: string): number => {
  const parsed = Number(value);
  return Number.isNaN(parsed) ? 0 : parsed;
};

const getSummary = (preview: CatalogImportPreview | null, fallbackRows: number, fallbackErrors: number) => {
  const summary = preview?.summary;
  return {
    rowsParsed: resolveSummaryValue(summary?.rowsParsed ?? fallbackRows),
    willCreate: resolveSummaryValue(summary?.willCreate),
    willUpdate: resolveSummaryValue(summary?.willUpdate),
    errorsCount: resolveSummaryValue(summary?.errorsCount ?? fallbackErrors),
  };
};

export function ServicesCatalogPageProd() {
  const { user } = useAuth();
  const { portal } = usePortal();
  const { t } = useTranslation();
  const effectiveRoles = resolveEffectivePartnerRoles(portal, user?.roles);
  const canRead = canReadServices(effectiveRoles);
  const canManage = canManageServices(effectiveRoles);
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const [reloadKey, setReloadKey] = useState(0);
  const [filters, setFilters] = useState({
    q: "",
    kind: "ALL",
    status: "ALL",
    category: "",
  });
  const [error, setError] = useState<unknown>(null);
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
    } catch (err) {
      if (DEBUG_SERVICE_CATALOG_ERRORS) {
        console.error(err);
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

  const refreshCatalogList = () => {
    setPage(1);
    setReloadKey((value) => value + 1);
  };

  useEffect(() => {
    if (!user || !canRead) return;
    fetchItems();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, canRead, page, pageSize, filters, reloadKey]);

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
      setFormError({ message: t("marketplace.servicesCatalogPage.errors.requiredFields") });
      return;
    }
    setFormError(null);
    setActionNotice(null);
    setActionCorrelation(null);
    try {
      const payload = buildCatalogPayload({ ...formState, status: activate ? "ACTIVE" : formState.status });
      if (editingItem) {
        const result = await updateCatalogItem(user.token, editingItem.id, payload);
        setActionNotice(t("marketplace.servicesCatalogPage.notifications.saved"));
        setActionCorrelation(result.correlationId ?? null);
        setItems((prev) => prev.map((item) => (item.id === editingItem.id ? result.data : item)));
      } else {
        const result = await createCatalogItem(user.token, payload);
        setActionNotice(t("marketplace.servicesCatalogPage.notifications.created"));
        setActionCorrelation(result.correlationId ?? null);
        setItems((prev) => [result.data, ...prev]);
        setTotal((prev) => prev + 1);
      }
      setModalOpen(false);
    } catch (err) {
      setFormError(normalizeError(err, t("marketplace.servicesCatalogPage.errors.saveFailed")));
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
        setActionNotice(t("marketplace.servicesCatalogPage.notifications.disabled"));
        setActionCorrelation(result.correlationId ?? null);
      } else {
        const result = await activateCatalogItem(user.token, item.id);
        setItems((prev) => prev.map((entry) => (entry.id === item.id ? { ...entry, status: "ACTIVE" } : entry)));
        setActionNotice(t("marketplace.servicesCatalogPage.notifications.activated"));
        setActionCorrelation(result.correlationId ?? null);
      }
    } catch (err) {
      setError(normalizeError(err, t("marketplace.servicesCatalogPage.errors.updateStatusFailed")));
    }
  };

  const handlePreviewImport = async () => {
    if (!user || !importFile) {
      setImportError({ message: t("marketplace.servicesCatalogPage.import.errors.selectCsv") });
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
        setImportParsingErrors(parsed.errors.map((row) => t("marketplace.servicesCatalogPage.import.errors.row", { row: row.row, message: row.message })));
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
      setImportError(normalizeError(err, t("marketplace.servicesCatalogPage.import.errors.previewFailed")));
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
      setImportError(normalizeError(err, t("marketplace.servicesCatalogPage.import.errors.applyFailed")));
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
        <div className="page-section">
          <div className="page-section__header">
            <div>
              <h2>{t("marketplace.servicesCatalogPage.title")}</h2>
              <div className="muted">{t("marketplace.servicesCatalogPage.subtitle")}</div>
            </div>
            {canManage ? (
              <button type="button" className="primary" onClick={openCreateModal}>
                {t("actions.create")}
              </button>
            ) : null}
          </div>
          <div className="page-section__content">
            <div className="filters neft-filters">
              <label className="filter neft-filter">
                {t("marketplace.servicesCatalogPage.filters.search")}
                <input
                  type="search"
                  placeholder={t("marketplace.servicesCatalogPage.filters.searchPlaceholder")}
                  value={filters.q}
                  onChange={(event) => {
                    setFilters((prev) => ({ ...prev, q: event.target.value }));
                    setPage(1);
                  }}
                />
              </label>
              <label className="filter neft-filter">
                {t("marketplace.servicesCatalogPage.filters.kind")}
                <select
                  value={filters.kind}
                  onChange={(event) => {
                    setFilters((prev) => ({ ...prev, kind: event.target.value }));
                    setPage(1);
                  }}
                >
                  <option value="ALL">{t("common.all")}</option>
                  <option value="SERVICE">{t("marketplace.servicesCatalogPage.filters.kindOptions.service")}</option>
                  <option value="PRODUCT">{t("marketplace.servicesCatalogPage.filters.kindOptions.product")}</option>
                </select>
              </label>
              <label className="filter neft-filter">
                {t("marketplace.servicesCatalogPage.filters.status")}
                <select
                  value={filters.status}
                  onChange={(event) => {
                    setFilters((prev) => ({ ...prev, status: event.target.value }));
                    setPage(1);
                  }}
                >
                  <option value="ALL">{t("common.all")}</option>
                  <option value="DRAFT">{t("marketplace.servicesCatalogPage.filters.statusOptions.draft")}</option>
                  <option value="ACTIVE">{t("marketplace.servicesCatalogPage.filters.statusOptions.active")}</option>
                  <option value="DISABLED">{t("marketplace.servicesCatalogPage.filters.statusOptions.disabled")}</option>
                  <option value="ARCHIVED">{t("marketplace.servicesCatalogPage.filters.statusOptions.archived")}</option>
                </select>
              </label>
              <label className="filter neft-filter">
                {t("marketplace.servicesCatalogPage.filters.category")}
                <input
                  type="text"
                  placeholder={t("marketplace.servicesCatalogPage.filters.categoryPlaceholder")}
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
          </div>
        </div>
        {isLoading ? (
          <div className="skeleton-stack" aria-busy="true">
            <div className="skeleton-line" />
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        ) : error ? (
          <PartnerErrorState
            title={t("errors.unavailableTitle")}
            description={t("errors.unavailableDescription")}
            error={error}
            onRetry={refreshCatalogList}
          />
        ) : items.length === 0 ? (
          <EmptyState
            icon={<Wrench />}
            title={hasFilters ? t("marketplace.servicesCatalogPage.empty.filteredTitle") : t("emptyStates.servicesCatalog.title")}
            description={
              hasFilters ? t("marketplace.servicesCatalogPage.empty.filteredDescription") : t("emptyStates.servicesCatalog.description")
            }
            primaryAction={
              hasFilters
                ? {
                    label: t("marketplace.servicesCatalogPage.actions.resetFilters"),
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
            secondaryAction={
              hasFilters
                ? undefined
                : {
                    label: t("marketplace.servicesCatalogPage.import.refreshList"),
                    onClick: refreshCatalogList,
                  }
            }
          />
        ) : (
          <div className="page-section">
            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t("marketplace.servicesCatalogPage.table.title")}</th>
                    <th>{t("marketplace.servicesCatalogPage.table.kind")}</th>
                    <th>{t("marketplace.servicesCatalogPage.table.category")}</th>
                    <th>{t("marketplace.servicesCatalogPage.table.status")}</th>
                    <th>{t("marketplace.servicesCatalogPage.table.activeOffers")}</th>
                    <th>{t("marketplace.servicesCatalogPage.table.updatedAt")}</th>
                    <th>{t("marketplace.servicesCatalogPage.table.actions")}</th>
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
                                {item.status === "ACTIVE" ? t("marketplace.servicesCatalogPage.actions.disable") : t("marketplace.servicesCatalogPage.actions.activate")}
                              </button>
                            </>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="table-footer">
              <div className="table-footer__content">
                <span className="muted">{items.length} / {total}</span>
                <div className="pagination pagination-wrapper">
                  <button type="button" className="secondary" onClick={() => setPage((prev) => Math.max(prev - 1, 1))} disabled={page <= 1}>
                    {t("marketplace.servicesCatalogPage.pagination.prev")}
                  </button>
                  <div className="muted">
                    {t("marketplace.servicesCatalogPage.pagination.page")} {page} / {totalPages}
                  </div>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))}
                    disabled={page >= totalPages}
                  >
                    {t("marketplace.servicesCatalogPage.pagination.next")}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </section>

      <section className="card import-section">
        <div className="page-section__header">
          <div>
            <h3>{t("marketplace.servicesCatalogPage.import.title")}</h3>
            <div className="muted">{t("marketplace.servicesCatalogPage.import.subtitle")}</div>
          </div>
        </div>
        {!canManage ? (
          <EmptyState
            icon={<Wrench />}
            title={t("marketplace.servicesCatalogPage.import.unavailableTitle")}
            description={t("marketplace.servicesCatalogPage.import.unavailableDescription")}
          />
        ) : (
          <div className="page-section__content">
            <div className="form-grid neft-import-grid">
              <label className="form-field">
                {t("marketplace.servicesCatalogPage.import.csvFile")}
                <input
                  type="file"
                  accept=".csv,text/csv"
                  onChange={(event) => setImportFile(event.target.files?.[0] ?? null)}
                />
              </label>
              <label className="form-field">
                {t("marketplace.servicesCatalogPage.import.mode")}
                <select value={importMode} onChange={(event) => setImportMode(event.target.value as ImportMode)}>
                  <option value="create">{t("marketplace.servicesCatalogPage.import.modes.create")}</option>
                  <option value="upsert">{t("marketplace.servicesCatalogPage.import.modes.upsert")}</option>
                </select>
              </label>
              <div className="form-grid__actions">
                <button type="button" className="secondary" onClick={handlePreviewImport} disabled={importLoading}>
                  {t("marketplace.servicesCatalogPage.import.preview")}
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
                <div>{t("marketplace.servicesCatalogPage.import.csvError")}</div>
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
                  <div className="label">{t("marketplace.servicesCatalogPage.import.previewSummary")}</div>
                  <div className="grid two">
                    <div>{t("marketplace.servicesCatalogPage.import.rowsParsed", { count: toNum(previewSummary.rowsParsed) })}</div>
                    <div>{t("marketplace.servicesCatalogPage.import.willCreate", { count: toNum(previewSummary.willCreate) })}</div>
                    <div>{t("marketplace.servicesCatalogPage.import.willUpdate", { count: toNum(previewSummary.willUpdate) })}</div>
                    <div>{t("marketplace.servicesCatalogPage.import.errorsCount", { count: toNum(previewSummary.errorsCount) })}</div>
                  </div>
                </div>
                {importPreview.errors.length ? (
                  <div className="notice error">
                    <div className="label">{t("marketplace.servicesCatalogPage.import.errorsTitle")}</div>
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>{t("marketplace.servicesCatalogPage.import.table.row")}</th>
                          <th>{t("marketplace.servicesCatalogPage.import.table.description")}</th>
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
                    <div className="label">{t("marketplace.servicesCatalogPage.import.sampleTitle")}</div>
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
                    {t("marketplace.servicesCatalogPage.import.apply")}
                  </button>
                </div>
              </div>
            ) : null}
            {importApplyResult ? (
              <div className="notice">
                <div className="label">{t("marketplace.servicesCatalogPage.import.resultTitle")}</div>
                <div className="grid two">
                  <div>{t("marketplace.servicesCatalogPage.import.resultCreated", { count: importApplyResult.created })}</div>
                  <div>{t("marketplace.servicesCatalogPage.import.resultUpdated", { count: importApplyResult.updated })}</div>
                  <div>{t("marketplace.servicesCatalogPage.import.resultSkipped", { count: importApplyResult.skipped })}</div>
                </div>
                <button type="button" className="link-button" onClick={refreshCatalogList}>
                  {t("marketplace.servicesCatalogPage.import.refreshList")}
                </button>
              </div>
            ) : null}
            <div className="notice">
              <div className="label">{t("marketplace.servicesCatalogPage.import.csvFormat")}</div>
              <div className="muted">{t("marketplace.servicesCatalogPage.import.requiredFields")}</div>
              <pre className="code-block">
                kind,title,category,uom,description,status{"\n"}
                {t("marketplace.servicesCatalogPage.import.sampleRow")}
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
                {editingItem ? t("marketplace.servicesCatalogPage.modal.editTitle") : t("marketplace.servicesCatalogPage.modal.createTitle")}
              </h3>
              <button type="button" className="ghost" onClick={() => setModalOpen(false)}>
                {t("actions.close")}
              </button>
            </div>
            <div className="form-grid">
              <label className="form-field">
                {t("marketplace.servicesCatalogPage.modal.fields.title")}
                <input
                  type="text"
                  value={formState.title}
                  onChange={(event) => setFormState((prev) => ({ ...prev, title: event.target.value }))}
                />
              </label>
              <label className="form-field">
                {t("marketplace.servicesCatalogPage.modal.fields.kind")}
                <select value={formState.kind} onChange={(event) => setFormState((prev) => ({ ...prev, kind: event.target.value as CatalogItemKind }))}>
                  <option value="SERVICE">SERVICE</option>
                  <option value="PRODUCT">PRODUCT</option>
                </select>
              </label>
              <label className="form-field">
                {t("marketplace.servicesCatalogPage.modal.fields.category")}
                <input
                  type="text"
                  value={formState.category}
                  onChange={(event) => setFormState((prev) => ({ ...prev, category: event.target.value }))}
                />
              </label>
              <label className="form-field">
                {t("marketplace.servicesCatalogPage.modal.fields.uom")}
                <input
                  type="text"
                  placeholder={t("marketplace.servicesCatalogPage.modal.fields.uomPlaceholder")}
                  value={formState.baseUom}
                  onChange={(event) => setFormState((prev) => ({ ...prev, baseUom: event.target.value }))}
                />
              </label>
              <label className="form-field form-grid__full">
                {t("marketplace.servicesCatalogPage.modal.fields.description")}
                <textarea
                  className="textarea"
                  rows={3}
                  value={formState.description}
                  onChange={(event) => setFormState((prev) => ({ ...prev, description: event.target.value }))}
                />
              </label>
              <label className="form-field">
                {t("marketplace.servicesCatalogPage.modal.fields.status")}
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
                  {t("marketplace.servicesCatalogPage.modal.actions.saveActivate")}
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
