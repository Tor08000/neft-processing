import { useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { fetchPriceVersion, fetchPriceVersionAudit, fetchPriceVersionDiff, fetchPriceVersionItems, fetchPriceVersions, importPriceVersion, publishPriceVersion, rollbackPriceVersion, validatePriceVersion } from "../api/prices";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ErrorState, ForbiddenState, LoadingState } from "../components/states";
import type { DiffResult, PriceAuditEvent, PriceItem, PriceVersion, ValidationResult } from "../types/prices";
import { formatDateTime } from "../utils/format";
import { canCreateDraftPrices, canPublishPrices, canReadPrices } from "../utils/roles";
import { parseCsv } from "../utils/csv";
import { ApiError } from "../api/http";
import { StatusBadge } from "../components/StatusBadge";

const tabs = ["overview", "import", "preview", "validate", "diff", "audit"] as const;
type TabKey = (typeof tabs)[number];

const shortId = (value: string) => value.slice(0, 8);

export function PriceVersionDetailsPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [version, setVersion] = useState<PriceVersion | null>(null);
  const [versions, setVersions] = useState<PriceVersion[]>([]);
  const [items, setItems] = useState<PriceItem[]>([]);
  const [itemsTotal, setItemsTotal] = useState<number | null>(null);
  const [auditEvents, setAuditEvents] = useState<PriceAuditEvent[]>([]);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [diffResult, setDiffResult] = useState<DiffResult | null>(null);
  const [diffTarget, setDiffTarget] = useState("");
  const [page, setPage] = useState(1);
  const [errorsOnly, setErrorsOnly] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [uploadFormat, setUploadFormat] = useState<"CSV" | "JSON">("CSV");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadPreview, setUploadPreview] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionCorrelation, setActionCorrelation] = useState<string | null>(null);
  const [isActionLoading, setIsActionLoading] = useState(false);

  const canRead = canReadPrices(user?.roles);
  const canImport = canCreateDraftPrices(user?.roles);
  const canPublish = canPublishPrices(user?.roles);

  const tab = (searchParams.get("tab") as TabKey) ?? "overview";

  useEffect(() => {
    if (!tabs.includes(tab)) {
      setSearchParams({ tab: "overview" });
    }
  }, [tab, setSearchParams]);

  useEffect(() => {
    let active = true;
    if (!user || !id || !canRead) return;
    setIsLoading(true);
    Promise.all([fetchPriceVersion(user.token, id), fetchPriceVersions(user.token, {})])
      .then(([detail, list]) => {
        if (!active) return;
        setVersion(detail);
        setVersions(list.items ?? []);
        setError(null);
      })
      .catch((err) => {
        console.error(err);
        if (active) {
          setError(err instanceof ApiError ? err : new ApiError("Не удалось загрузить версию", 500, null));
        }
      })
      .finally(() => {
        if (active) {
          setIsLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [user, id, canRead]);

  useEffect(() => {
    if (!user || !id || tab !== "preview") return;
    fetchPriceVersionItems(user.token, id, {
      limit: 20,
      offset: (page - 1) * 20,
      errors_only: errorsOnly ? 1 : 0,
      search: searchQuery,
    })
      .then((response) => {
        setItems(response.items ?? []);
        setItemsTotal(response.total ?? null);
      })
      .catch((err) => {
        console.error(err);
      });
  }, [user, id, tab, page, errorsOnly, searchQuery]);

  useEffect(() => {
    if (!user || !id || tab !== "audit") return;
    fetchPriceVersionAudit(user.token, id)
      .then((response) => {
        setAuditEvents(response.items ?? []);
      })
      .catch((err) => {
        console.error(err);
      });
  }, [user, id, tab]);

  useEffect(() => {
    if (!user || !id || tab !== "diff" || !diffTarget) return;
    fetchPriceVersionDiff(user.token, id, diffTarget)
      .then((response) => setDiffResult(response))
      .catch((err) => {
        console.error(err);
      });
  }, [user, id, tab, diffTarget]);

  useEffect(() => {
    if (!uploadFile) {
      setUploadPreview(null);
      return;
    }
    if (uploadFormat === "CSV") {
      uploadFile.text().then((text) => {
        const result = parseCsv(text);
        if (result.errors.length) {
          setUploadPreview(`Найдено ошибок: ${result.errors.length}`);
        } else {
          setUploadPreview(`Строк: ${result.rows.length}`);
        }
      });
    } else {
      uploadFile.text().then((text) => {
        try {
          const parsed = JSON.parse(text) as unknown;
          const rowsCount = Array.isArray(parsed) ? parsed.length : 0;
          setUploadPreview(`JSON записей: ${rowsCount}`);
        } catch (err) {
          setUploadPreview("Ошибка JSON формата");
        }
      });
    }
  }, [uploadFile, uploadFormat]);

  const availableDiffTargets = useMemo(
    () => versions.filter((candidate) => candidate.id !== id),
    [versions, id],
  );

  const handleValidate = async () => {
    if (!user || !id) return;
    if (!window.confirm("Запустить валидацию версии?")) return;
    setIsActionLoading(true);
    setActionMessage(null);
    setActionCorrelation(null);
    try {
      const response = await validatePriceVersion(user.token, id);
      setValidation(response.data);
      setActionMessage(response.data.ok ? "Валидация пройдена" : "Валидация завершена с ошибками");
      setActionCorrelation(response.correlationId);
    } catch (err) {
      console.error(err);
      if (err instanceof ApiError) {
        setActionMessage(`Ошибка: ${err.message} (status ${err.status})`);
        setActionCorrelation(err.correlationId);
      } else {
        setActionMessage("Не удалось запустить валидацию");
      }
    } finally {
      setIsActionLoading(false);
    }
  };

  const handlePublish = async () => {
    if (!user || !id) return;
    if (!window.confirm("Опубликовать эту версию?")) return;
    setIsActionLoading(true);
    setActionMessage(null);
    setActionCorrelation(null);
    try {
      const response = await publishPriceVersion(user.token, id);
      setVersion(response.data);
      setActionMessage("Версия опубликована");
      setActionCorrelation(response.correlationId);
    } catch (err) {
      console.error(err);
      if (err instanceof ApiError) {
        setActionMessage(`Ошибка: ${err.message} (status ${err.status})`);
        setActionCorrelation(err.correlationId);
      } else {
        setActionMessage("Не удалось опубликовать версию");
      }
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleRollback = async () => {
    if (!user || !id) return;
    if (!window.confirm("Создать rollback на эту версию?")) return;
    setIsActionLoading(true);
    setActionMessage(null);
    setActionCorrelation(null);
    try {
      const response = await rollbackPriceVersion(user.token, id);
      setVersion(response.data);
      setActionMessage("Rollback создан");
      setActionCorrelation(response.correlationId);
    } catch (err) {
      console.error(err);
      if (err instanceof ApiError) {
        setActionMessage(`Ошибка: ${err.message} (status ${err.status})`);
        setActionCorrelation(err.correlationId);
      } else {
        setActionMessage("Не удалось выполнить rollback");
      }
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleImport = async () => {
    if (!user || !id || !uploadFile) return;
    if (!window.confirm("Импортировать файл в версию?")) return;
    setIsActionLoading(true);
    setActionMessage(null);
    setActionCorrelation(null);
    try {
      const content = await uploadFile.arrayBuffer();
      const base64 = btoa(String.fromCharCode(...new Uint8Array(content)));
      const response = await importPriceVersion(user.token, id, { format: uploadFormat, content_base64: base64 });
      setActionMessage(`Импорт завершён. Ошибок: ${response.data.errors_found}`);
      setActionCorrelation(response.correlationId);
    } catch (err) {
      console.error(err);
      if (err instanceof ApiError) {
        setActionMessage(`Ошибка: ${err.message} (status ${err.status})`);
        setActionCorrelation(err.correlationId);
      } else {
        setActionMessage("Не удалось импортировать файл");
      }
    } finally {
      setIsActionLoading(false);
    }
  };

  if (!canRead) {
    return <ForbiddenState description="Роль не позволяет просматривать версию цен." />;
  }

  if (isLoading) {
    return <LoadingState label="Загружаем версию цен..." />;
  }

  if (error) {
    return (
      <ErrorState
        title={`Ошибка загрузки (status ${error.status})`}
        description={error.message}
        correlationId={error.correlationId}
        action={
          <button type="button" onClick={() => window.location.reload()}>
            Повторить
          </button>
        }
      />
    );
  }

  if (!version) {
    return (
      <EmptyState
        title="Версия не найдена"
        description="Проверьте идентификатор версии и повторите запрос."
      />
    );
  }

  const isValidated = version.status === "VALIDATED";
  const publishDisabled = !isValidated || validation?.errors_total;

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <div>
            <h2>Версия {shortId(version.id)}</h2>
            <p className="muted">Статус и управление версией прайса.</p>
          </div>
          <div className="actions">
            <button type="button" onClick={handleValidate} disabled={!canImport || isActionLoading}>
              Валидировать
            </button>
            {canPublish ? (
              <button
                type="button"
                className="primary"
                onClick={handlePublish}
                disabled={publishDisabled || isActionLoading}
              >
                Публиковать
              </button>
            ) : null}
            {canPublish ? (
              <button
                type="button"
                onClick={handleRollback}
                disabled={version.status !== "PUBLISHED" || isActionLoading}
              >
                Rollback
              </button>
            ) : null}
          </div>
        </div>
        {actionMessage ? (
          <div className="notice">
            <strong>{actionMessage}</strong>
            {actionCorrelation ? <div className="muted">Correlation ID: {actionCorrelation}</div> : null}
          </div>
        ) : null}
      </section>

      <section className="card">
        <div className="tabs">
          {tabs.map((tabKey) => (
            <button
              key={tabKey}
              type="button"
              className={`tab${tab === tabKey ? " active" : ""}`}
              onClick={() => setSearchParams({ tab: tabKey })}
            >
              {tabKey}
            </button>
          ))}
        </div>

        {tab === "overview" ? (
          <div className="meta-grid">
            <div>
              <div className="label">Статус</div>
              <StatusBadge status={version.status.toLowerCase()} />
            </div>
            <div>
              <div className="label">Scope</div>
              <div>{version.station_scope === "all" ? "Все станции" : `${version.station_ids?.length ?? 0} станций`}</div>
            </div>
            <div>
              <div className="label">Items</div>
              <div>{version.item_count}</div>
            </div>
            <div>
              <div className="label">Errors</div>
              <div>{version.error_count}</div>
            </div>
            <div>
              <div className="label">Создано</div>
              <div>{formatDateTime(version.created_at)}</div>
            </div>
            <div>
              <div className="label">Создатель</div>
              <div>{version.created_by ?? "—"}</div>
            </div>
            <div>
              <div className="label">Опубликовано</div>
              <div>{formatDateTime(version.publish_at)}</div>
            </div>
            <div>
              <div className="label">Checksum</div>
              <div>{version.checksum_sha256 ?? "—"}</div>
            </div>
          </div>
        ) : null}

        {tab === "import" ? (
          <div className="stack">
            <div className="card">
              <h3>Формат CSV</h3>
              <p className="muted">Обязательные поля: station_code (или station_id), product_code, price, currency, valid_from.</p>
              <pre className="code-block">
                station_code,product_code,price,currency,valid_from,valid_to,vat_rate
                {"\n"}AZS-001,FUEL-95,52.4,RUB,2024-02-01,,20
              </pre>
            </div>
            <div className="form-grid">
              <label className="form-field">
                <span className="label">Формат</span>
                <select value={uploadFormat} onChange={(event) => setUploadFormat(event.target.value as "CSV" | "JSON")}>
                  <option value="CSV">CSV</option>
                  <option value="JSON">JSON</option>
                </select>
              </label>
              <label className="form-field form-grid__full">
                <span className="label">Файл</span>
                <input type="file" accept={uploadFormat === "CSV" ? ".csv" : ".json,application/json"} onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)} />
              </label>
            </div>
            {uploadPreview ? <p className="muted">Preview: {uploadPreview}</p> : null}
            <div className="actions">
              <button type="button" onClick={handleImport} disabled={!uploadFile || !canImport || isActionLoading}>
                Commit import to version
              </button>
            </div>
          </div>
        ) : null}

        {tab === "preview" ? (
          <div className="stack">
            <div className="form-grid">
              <label className="form-field">
                <span className="label">Поиск</span>
                <input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="station/product" />
              </label>
              <label className="form-field">
                <span className="label">Errors only</span>
                <input type="checkbox" checked={errorsOnly} onChange={(event) => setErrorsOnly(event.target.checked)} />
              </label>
            </div>
            {items.length === 0 ? (
              <EmptyState title="Нет элементов" description="Элементы появятся после импорта." />
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Station</th>
                    <th>Product</th>
                    <th>Price</th>
                    <th>Currency</th>
                    <th>Valid from</th>
                    <th>Errors</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item, index) => (
                    <tr key={`${item.station_id ?? item.station_code ?? "row"}-${index}`}>
                      <td>{item.station_code ?? item.station_id ?? "—"}</td>
                      <td>{item.product_code}</td>
                      <td>{item.price}</td>
                      <td>{item.currency}</td>
                      <td>{item.valid_from}</td>
                      <td>{item.errors?.length ?? 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <div className="actions">
              <button type="button" onClick={() => setPage(Math.max(1, page - 1))} disabled={page === 1}>
                Назад
              </button>
              <span className="muted">
                Страница {page}
                {itemsTotal ? ` из ${Math.ceil(itemsTotal / 20)}` : ""}
              </span>
              <button type="button" onClick={() => setPage(page + 1)} disabled={items.length < 20}>
                Вперёд
              </button>
            </div>
          </div>
        ) : null}

        {tab === "validate" ? (
          <div className="stack">
            <button type="button" onClick={handleValidate} disabled={!canImport || isActionLoading}>
              Run validation
            </button>
            {validation ? (
              <div className="meta-grid">
                <div>
                  <div className="label">OK</div>
                  <div>{validation.ok ? "Да" : "Нет"}</div>
                </div>
                <div>
                  <div className="label">Errors</div>
                  <div>{validation.errors_total}</div>
                </div>
                <div>
                  <div className="label">Warnings</div>
                  <div>{validation.warnings_total}</div>
                </div>
              </div>
            ) : (
              <EmptyState title="Валидация не запускалась" description="Запустите валидацию для получения отчёта." />
            )}
            {validation?.sample_errors?.length ? (
              <div>
                <h4>Sample errors</h4>
                <ul className="bullets">
                  {validation.sample_errors.map((errorItem, index) => (
                    <li key={`${errorItem.code}-${index}`}>{errorItem.message}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {validation?.recommended_actions?.length ? (
              <div>
                <h4>Recommended actions</h4>
                <ul className="bullets">
                  {validation.recommended_actions.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : null}

        {tab === "diff" ? (
          <div className="stack">
            <label className="form-field">
              <span className="label">Compare to version</span>
              <select value={diffTarget} onChange={(event) => setDiffTarget(event.target.value)}>
                <option value="">Выберите версию</option>
                {availableDiffTargets.map((candidate) => (
                  <option key={candidate.id} value={candidate.id}>
                    {shortId(candidate.id)} — {candidate.status}
                  </option>
                ))}
              </select>
            </label>
            {diffResult ? (
              <div className="stack">
                <div className="meta-grid">
                  <div>
                    <div className="label">Добавлено</div>
                    <div>{diffResult.added_count}</div>
                  </div>
                  <div>
                    <div className="label">Удалено</div>
                    <div>{diffResult.removed_count}</div>
                  </div>
                  <div>
                    <div className="label">Изменено</div>
                    <div>{diffResult.changed_count}</div>
                  </div>
                </div>
                {diffResult.sample_changed?.length ? (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Station</th>
                        <th>Product</th>
                        <th>Before</th>
                        <th>After</th>
                      </tr>
                    </thead>
                    <tbody>
                      {diffResult.sample_changed.map((item, index) => (
                        <tr key={`${item.product_code}-${index}`}>
                          <td>{item.station_code ?? item.station_id ?? "—"}</td>
                          <td>{item.product_code}</td>
                          <td>{item.before ? JSON.stringify(item.before) : "—"}</td>
                          <td>{item.after ? JSON.stringify(item.after) : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <EmptyState title="Нет изменений" description="Выберите другую версию для сравнения." />
                )}
              </div>
            ) : (
              <EmptyState title="Выберите версию" description="Выберите версию для расчёта diff." />
            )}
          </div>
        ) : null}

        {tab === "audit" ? (
          <div className="stack">
            {auditEvents.length === 0 ? (
              <EmptyState title="Нет событий" description="Аудит появится после действий с версией." />
            ) : (
              <div className="timeline-list">
                {auditEvents.map((eventItem) => (
                  <div className="timeline-item" key={eventItem.id}>
                    <div className="timeline-item__meta">
                      <span className="timeline-item__title">{eventItem.action}</span>
                      <span className="muted">{formatDateTime(eventItem.created_at)}</span>
                    </div>
                    <div className="timeline-item__body">
                      <span>Actor: {eventItem.actor ?? "system"}</span>
                      {eventItem.correlation_id ? <span className="muted">Correlation ID: {eventItem.correlation_id}</span> : null}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : null}
      </section>
    </div>
  );
}
