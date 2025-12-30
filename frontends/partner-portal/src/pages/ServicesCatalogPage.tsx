import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
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
import { EmptyState, ErrorState, ForbiddenState } from "../components/states";
import { StatusBadge } from "../components/StatusBadge";
import { formatDateTime, formatNumber } from "../utils/format";
import { parseCatalogCsv } from "../utils/csv";
import { canManageServices, canReadServices } from "../utils/roles";
import type { CatalogItem, CatalogItemInput, CatalogItemKind, CatalogItemStatus, CatalogImportPreview } from "../types/marketplace";

type ApiErrorState = {
  message: string;
  status?: number;
  correlationId?: string | null;
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
    return { message: error.message, status: error.status, correlationId: error.correlationId };
  }
  if (error instanceof Error) {
    return { message: error.message };
  }
  return { message: fallback };
};

const formatErrorDescription = (error: ApiErrorState): string => {
  if (error.status) {
    return `${error.message} (HTTP ${error.status})`;
  }
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
  const [error, setError] = useState<ApiErrorState | null>(null);
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
    correlationId?: string | null;
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
      setError(normalizeError(err, "Не удалось загрузить каталог"));
    } finally {
      setIsLoading(false);
    }
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
      setFormError({ message: "Заполните обязательные поля" });
      return;
    }
    setFormError(null);
    setActionNotice(null);
    setActionCorrelation(null);
    try {
      const payload = buildCatalogPayload({ ...formState, status: activate ? "ACTIVE" : formState.status });
      if (editingItem) {
        const result = await updateCatalogItem(user.token, editingItem.id, payload);
        setActionNotice("Изменения сохранены");
        setActionCorrelation(result.correlationId ?? null);
        setItems((prev) => prev.map((item) => (item.id === editingItem.id ? result.data : item)));
      } else {
        const result = await createCatalogItem(user.token, payload);
        setActionNotice("Элемент каталога создан");
        setActionCorrelation(result.correlationId ?? null);
        setItems((prev) => [result.data, ...prev]);
        setTotal((prev) => prev + 1);
      }
      setModalOpen(false);
    } catch (err) {
      setFormError(normalizeError(err, "Не удалось сохранить элемент"));
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
        setActionNotice("Элемент каталога отключён");
        setActionCorrelation(result.correlationId ?? null);
      } else {
        const result = await activateCatalogItem(user.token, item.id);
        setItems((prev) => prev.map((entry) => (entry.id === item.id ? { ...entry, status: "ACTIVE" } : entry)));
        setActionNotice("Элемент каталога активирован");
        setActionCorrelation(result.correlationId ?? null);
      }
    } catch (err) {
      setError(normalizeError(err, "Не удалось изменить статус"));
    }
  };

  const handlePreviewImport = async () => {
    if (!user || !importFile) {
      setImportError({ message: "Выберите CSV файл" });
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
        setImportParsingErrors(parsed.errors.map((row) => `Строка ${row.row}: ${row.message}`));
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
        correlationId: preview.correlationId ?? null,
      });
    } catch (err) {
      setImportError(normalizeError(err, "Не удалось выполнить preview"));
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
        correlationId: result.correlationId ?? null,
      });
      setImportPreview(null);
    } catch (err) {
      setImportError(normalizeError(err, "Не удалось применить импорт"));
    } finally {
      setImportApplyLoading(false);
    }
  };

  const resetFilters = () => {
    setFilters({ q: "", kind: "ALL", status: "ALL", category: "" });
    setPage(1);
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
            <h2>Каталог услуг и товаров</h2>
            <div className="muted">Marketplace partner catalog</div>
          </div>
          {canManage ? (
            <button type="button" className="primary" onClick={openCreateModal}>
              Создать
            </button>
          ) : null}
        </div>
        <div className="filters">
          <label className="filter">
            Поиск
            <input
              type="search"
              placeholder="Название, описание"
              value={filters.q}
              onChange={(event) => {
                setFilters((prev) => ({ ...prev, q: event.target.value }));
                setPage(1);
              }}
            />
          </label>
          <label className="filter">
            Тип
            <select
              value={filters.kind}
              onChange={(event) => {
                setFilters((prev) => ({ ...prev, kind: event.target.value }));
                setPage(1);
              }}
            >
              <option value="ALL">Все</option>
              <option value="SERVICE">Service</option>
              <option value="PRODUCT">Product</option>
            </select>
          </label>
          <label className="filter">
            Статус
            <select
              value={filters.status}
              onChange={(event) => {
                setFilters((prev) => ({ ...prev, status: event.target.value }));
                setPage(1);
              }}
            >
              <option value="ALL">Все</option>
              <option value="DRAFT">Draft</option>
              <option value="ACTIVE">Active</option>
              <option value="DISABLED">Disabled</option>
              <option value="ARCHIVED">Archived</option>
            </select>
          </label>
          <label className="filter">
            Категория
            <input
              type="text"
              placeholder="Например, автомойка"
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
            {actionCorrelation ? <div className="muted small">Correlation ID: {actionCorrelation}</div> : null}
          </div>
        ) : null}
        {isLoading ? (
          <div className="skeleton-stack" aria-busy="true">
            <div className="skeleton-line" />
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        ) : error ? (
          <ErrorState description={formatErrorDescription(error)} correlationId={error.correlationId} action={
            <button type="button" className="secondary" onClick={fetchItems}>
              Повторить
            </button>
          } />
        ) : items.length === 0 ? (
          <EmptyState
            title={hasFilters ? "Нет результатов фильтра" : "Каталог пуст"}
            description={
              hasFilters
                ? "Измените фильтры или сбросьте настройки поиска."
                : "Создайте первый каталог товаров или услуг для партнёра."
            }
            action={
              hasFilters ? (
                <button type="button" className="secondary" onClick={resetFilters}>
                  Сбросить фильтры
                </button>
              ) : canManage ? (
                <button type="button" className="primary" onClick={openCreateModal}>
                  Создать
                </button>
              ) : null
            }
          />
        ) : (
          <>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Название</th>
                  <th>Тип</th>
                  <th>Категория</th>
                  <th>Статус</th>
                  <th>Активные офферы</th>
                  <th>Обновлено</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.title}</td>
                    <td>{item.kind}</td>
                    <td>{item.category ?? "—"}</td>
                    <td>
                      <StatusBadge status={item.status} tone={resolveCatalogTone(item.status)} />
                    </td>
                    <td>{formatNumber(item.activeOffersCount ?? null)}</td>
                    <td>{formatDateTime(item.updatedAt)}</td>
                    <td>
                      <div className="stack-inline">
                        <Link to={`/services/${item.id}`} className="link-button">
                          Открыть
                        </Link>
                        {canManage ? (
                          <>
                            <button type="button" className="ghost" onClick={() => openEditModal(item)}>
                              Edit
                            </button>
                            <button type="button" className="ghost" onClick={() => handleToggleStatus(item)}>
                              {item.status === "ACTIVE" ? "Disable" : "Activate"}
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
                Назад
              </button>
              <div className="muted">
                Страница {page} из {totalPages}
              </div>
              <button
                type="button"
                className="secondary"
                onClick={() => setPage((prev) => Math.min(prev + 1, totalPages))}
                disabled={page >= totalPages}
              >
                Вперёд
              </button>
            </div>
          </>
        )}
      </section>

      <section className="card">
        <div className="section-title">
          <h3>Импорт каталога</h3>
          <div className="muted">CSV import with preview</div>
        </div>
        {!canManage ? (
          <EmptyState title="Импорт недоступен" description="Доступ только для PARTNER_OWNER или PARTNER_SERVICE_MANAGER." />
        ) : (
          <div className="stack">
            <div className="form-grid">
              <label className="form-field">
                CSV файл
                <input
                  type="file"
                  accept=".csv,text/csv"
                  onChange={(event) => setImportFile(event.target.files?.[0] ?? null)}
                />
              </label>
              <label className="form-field">
                Режим
                <select value={importMode} onChange={(event) => setImportMode(event.target.value as ImportMode)}>
                  <option value="create">create-only</option>
                  <option value="upsert">upsert</option>
                </select>
              </label>
              <div className="form-grid__actions">
                <button type="button" className="secondary" onClick={handlePreviewImport} disabled={importLoading}>
                  Preview
                </button>
              </div>
            </div>
            {importError ? (
              <div className="notice error">
                {formatErrorDescription(importError)}
                {importError.correlationId ? (
                  <div className="muted small">Correlation ID: {importError.correlationId}</div>
                ) : null}
              </div>
            ) : null}
            {importParsingErrors.length ? (
              <div className="notice error">
                <div>Ошибка CSV:</div>
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
                  <div className="label">Preview summary</div>
                  <div className="grid two">
                    <div>Rows parsed: {previewSummary.rowsParsed}</div>
                    <div>Will create: {previewSummary.willCreate}</div>
                    <div>Will update: {previewSummary.willUpdate}</div>
                    <div>Errors count: {previewSummary.errorsCount}</div>
                  </div>
                  {importPreview.correlationId ? (
                    <div className="muted small">Correlation ID: {importPreview.correlationId}</div>
                  ) : null}
                </div>
                {importPreview.errors.length ? (
                  <div className="notice error">
                    <div className="label">Ошибки импорта</div>
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Строка</th>
                          <th>Описание</th>
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
                    <div className="label">Пример строк (первые 20)</div>
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
                              <td key={`${index}-${columnIndex}`}>{value || "—"}</td>
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
                    Apply import
                  </button>
                </div>
              </div>
            ) : null}
            {importApplyResult ? (
              <div className="notice">
                <div className="label">Результат импорта</div>
                <div className="grid two">
                  <div>Created: {importApplyResult.created}</div>
                  <div>Updated: {importApplyResult.updated}</div>
                  <div>Skipped: {importApplyResult.skipped}</div>
                </div>
                {importApplyResult.correlationId ? (
                  <div className="muted small">Correlation ID: {importApplyResult.correlationId}</div>
                ) : null}
                <button type="button" className="link-button" onClick={fetchItems}>
                  Обновить список
                </button>
              </div>
            ) : null}
            <div className="notice">
              <div className="label">Формат CSV</div>
              <div className="muted">Обязательные поля: kind, title, category, uom</div>
              <pre className="code-block">
                kind,title,category,uom,description,status{"\n"}
                SERVICE,Услуга,Автомойка,услуга,Комплексная мойка,ACTIVE
              </pre>
            </div>
          </div>
        )}
      </section>

      {modalOpen ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal">
            <div className="card__header">
              <h3>{editingItem ? "Редактировать" : "Создать"} элемент</h3>
              <button type="button" className="ghost" onClick={() => setModalOpen(false)}>
                Close
              </button>
            </div>
            <div className="form-grid">
              <label className="form-field">
                Название *
                <input
                  type="text"
                  value={formState.title}
                  onChange={(event) => setFormState((prev) => ({ ...prev, title: event.target.value }))}
                />
              </label>
              <label className="form-field">
                Тип
                <select value={formState.kind} onChange={(event) => setFormState((prev) => ({ ...prev, kind: event.target.value as CatalogItemKind }))}>
                  <option value="SERVICE">SERVICE</option>
                  <option value="PRODUCT">PRODUCT</option>
                </select>
              </label>
              <label className="form-field">
                Категория
                <input
                  type="text"
                  value={formState.category}
                  onChange={(event) => setFormState((prev) => ({ ...prev, category: event.target.value }))}
                />
              </label>
              <label className="form-field">
                Ед. измерения *
                <input
                  type="text"
                  placeholder="шт / услуга / час"
                  value={formState.baseUom}
                  onChange={(event) => setFormState((prev) => ({ ...prev, baseUom: event.target.value }))}
                />
              </label>
              <label className="form-field form-grid__full">
                Описание
                <textarea
                  className="textarea"
                  rows={3}
                  value={formState.description}
                  onChange={(event) => setFormState((prev) => ({ ...prev, description: event.target.value }))}
                />
              </label>
              <label className="form-field">
                Статус
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
                {formError.correlationId ? (
                  <div className="muted small">Correlation ID: {formError.correlationId}</div>
                ) : null}
              </div>
            ) : null}
            <div className="form-actions">
              <button type="button" className="primary" onClick={() => handleSave(false)}>
                Save
              </button>
              {canManage ? (
                <button type="button" className="secondary" onClick={() => handleSave(true)}>
                  Save & Activate
                </button>
              ) : null}
              <button type="button" className="ghost" onClick={() => setModalOpen(false)}>
                Отмена
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
