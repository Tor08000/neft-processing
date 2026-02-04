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
import { useI18n } from "../i18n";

const tabs = ["overview", "import", "preview", "validate", "diff", "audit"] as const;
type TabKey = (typeof tabs)[number];

const shortId = (value: string) => value.slice(0, 8);

export function PriceVersionDetailsPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const { t } = useI18n();
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
          setError(
            err instanceof ApiError ? err : new ApiError(t("priceVersionPage.errors.loadFailed"), 500, null, null, null),
          );
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
          setUploadPreview(t("priceVersionPage.upload.csvErrors", { count: result.errors.length }));
        } else {
          setUploadPreview(t("priceVersionPage.upload.csvRows", { count: result.rows.length }));
        }
      });
    } else {
      uploadFile.text().then((text) => {
        try {
          const parsed = JSON.parse(text) as unknown;
          const rowsCount = Array.isArray(parsed) ? parsed.length : 0;
          setUploadPreview(t("priceVersionPage.upload.jsonRows", { count: rowsCount }));
        } catch (err) {
          setUploadPreview(t("priceVersionPage.upload.jsonError"));
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
    if (!window.confirm(t("priceVersionPage.confirmations.validate"))) return;
    setIsActionLoading(true);
    setActionMessage(null);
    setActionCorrelation(null);
    try {
      const response = await validatePriceVersion(user.token, id);
      setValidation(response.data);
      setActionMessage(response.data.ok ? t("priceVersionPage.notifications.validationOk") : t("priceVersionPage.notifications.validationWithErrors"));
      setActionCorrelation(response.correlationId);
    } catch (err) {
      console.error(err);
      if (err instanceof ApiError) {
        setActionMessage(t("priceVersionPage.errors.apiError", { message: err.message, status: err.status }));
        setActionCorrelation(err.correlationId);
      } else {
        setActionMessage(t("priceVersionPage.errors.validationFailed"));
      }
    } finally {
      setIsActionLoading(false);
    }
  };

  const handlePublish = async () => {
    if (!user || !id) return;
    if (!window.confirm(`${t("priceVersionPage.confirmations.publishTitle")}\n${t("priceVersionPage.confirmations.publishDescription")}`)) return;
    setIsActionLoading(true);
    setActionMessage(null);
    setActionCorrelation(null);
    try {
      const response = await publishPriceVersion(user.token, id);
      setVersion(response.data);
      setActionMessage(t("priceVersionPage.notifications.published"));
      setActionCorrelation(response.correlationId);
    } catch (err) {
      console.error(err);
      if (err instanceof ApiError) {
        setActionMessage(t("priceVersionPage.errors.apiError", { message: err.message, status: err.status }));
        setActionCorrelation(err.correlationId);
      } else {
        setActionMessage(t("priceVersionPage.errors.publishFailed"));
      }
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleRollback = async () => {
    if (!user || !id) return;
    if (!window.confirm(`${t("priceVersionPage.confirmations.rollbackTitle")}\n${t("priceVersionPage.confirmations.rollbackDescription")}`)) return;
    setIsActionLoading(true);
    setActionMessage(null);
    setActionCorrelation(null);
    try {
      const response = await rollbackPriceVersion(user.token, id);
      setVersion(response.data);
      setActionMessage(t("priceVersionPage.notifications.rollbackCreated"));
      setActionCorrelation(response.correlationId);
    } catch (err) {
      console.error(err);
      if (err instanceof ApiError) {
        setActionMessage(t("priceVersionPage.errors.apiError", { message: err.message, status: err.status }));
        setActionCorrelation(err.correlationId);
      } else {
        setActionMessage(t("priceVersionPage.errors.rollbackFailed"));
      }
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleImport = async () => {
    if (!user || !id || !uploadFile) return;
    if (!window.confirm(t("priceVersionPage.confirmations.import"))) return;
    setIsActionLoading(true);
    setActionMessage(null);
    setActionCorrelation(null);
    try {
      const content = await uploadFile.arrayBuffer();
      const base64 = btoa(String.fromCharCode(...new Uint8Array(content)));
      const response = await importPriceVersion(user.token, id, { format: uploadFormat, content_base64: base64 });
      setActionMessage(t("priceVersionPage.notifications.importCompleted", { errors: response.data.errors_found }));
      setActionCorrelation(response.correlationId);
    } catch (err) {
      console.error(err);
      if (err instanceof ApiError) {
        setActionMessage(t("priceVersionPage.errors.apiError", { message: err.message, status: err.status }));
        setActionCorrelation(err.correlationId);
      } else {
        setActionMessage(t("priceVersionPage.errors.importFailed"));
      }
    } finally {
      setIsActionLoading(false);
    }
  };

  if (!canRead) {
    return <ForbiddenState description={t("priceVersionPage.forbidden")} />;
  }

  if (isLoading) {
    return <LoadingState label={t("priceVersionPage.loading")} />;
  }

  if (error) {
    return (
      <ErrorState
        title={t("priceVersionPage.errors.loadTitle", { status: error.status })}
        description={error.message}
        correlationId={error.correlationId}
        action={
          <button type="button" onClick={() => window.location.reload()}>
            {t("errors.retry")}
          </button>
        }
      />
    );
  }

  if (!version) {
    return (
      <EmptyState
        title={t("priceVersionPage.empty.notFoundTitle")}
        description={t("priceVersionPage.empty.notFoundDescription")}
      />
    );
  }

  const isValidated = version.status === "VALIDATED";
  const publishDisabled = !isValidated || Boolean(validation?.errors_total);

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <div>
            <h2>{t("priceVersionPage.header.title", { id: shortId(version.id) })}</h2>
            <p className="muted">{t("priceVersionPage.header.subtitle")}</p>
          </div>
          <div className="actions">
            <button type="button" onClick={handleValidate} disabled={!canImport || isActionLoading}>
              {t("priceVersionPage.actions.validate")}
            </button>
            {canPublish ? (
              <button
                type="button"
                className="primary"
                onClick={handlePublish}
                disabled={publishDisabled || isActionLoading}
              >
                {t("actions.publish")}
              </button>
            ) : null}
            {canPublish ? (
              <button
                type="button"
                onClick={handleRollback}
                disabled={version.status !== "PUBLISHED" || isActionLoading}
              >
                {t("priceVersionPage.actions.rollback")}
              </button>
            ) : null}
          </div>
        </div>
        {actionMessage ? (
          <div className="notice">
            <strong>{actionMessage}</strong>
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
              <div className="label">{t("common.status")}</div>
              <StatusBadge status={version.status.toLowerCase()} />
            </div>
            <div>
              <div className="label">{t("priceVersionPage.overview.scope")}</div>
              <div>
                {version.station_scope === "all"
                  ? t("priceVersionPage.overview.scopeAll")
                  : t("priceVersionPage.overview.scopeCount", { count: version.station_ids?.length ?? 0 })}
              </div>
            </div>
            <div>
              <div className="label">{t("priceVersionPage.overview.items")}</div>
              <div>{version.item_count}</div>
            </div>
            <div>
              <div className="label">{t("priceVersionPage.overview.errors")}</div>
              <div>{version.error_count}</div>
            </div>
            <div>
              <div className="label">{t("priceVersionPage.overview.createdAt")}</div>
              <div>{formatDateTime(version.created_at)}</div>
            </div>
            <div>
              <div className="label">{t("priceVersionPage.overview.createdBy")}</div>
              <div>{version.created_by ?? t("common.notAvailable")}</div>
            </div>
            <div>
              <div className="label">{t("priceVersionPage.overview.publishedAt")}</div>
              <div>{formatDateTime(version.publish_at)}</div>
            </div>
            <div>
              <div className="label">Checksum</div>
              <div>{version.checksum_sha256 ?? t("common.notAvailable")}</div>
            </div>
          </div>
        ) : null}

        {tab === "import" ? (
          <div className="stack">
            <div className="card">
              <h3>{t("priceVersionPage.import.csvFormat")}</h3>
              <p className="muted">{t("priceVersionPage.import.requiredFields")}</p>
              <pre className="code-block">
                station_code,product_code,price,currency,valid_from,valid_to,vat_rate
                {"\n"}AZS-001,FUEL-95,52.4,RUB,2024-02-01,,20
              </pre>
            </div>
            <div className="form-grid">
              <label className="form-field">
                <span className="label">{t("priceVersionPage.import.format")}</span>
                <select value={uploadFormat} onChange={(event) => setUploadFormat(event.target.value as "CSV" | "JSON")}>
                  <option value="CSV">CSV</option>
                  <option value="JSON">JSON</option>
                </select>
              </label>
              <label className="form-field form-grid__full">
                <span className="label">{t("priceVersionPage.import.file")}</span>
                <input type="file" accept={uploadFormat === "CSV" ? ".csv" : ".json,application/json"} onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)} />
              </label>
            </div>
            {uploadPreview ? <p className="muted">{t("priceVersionPage.import.preview", { text: uploadPreview })}</p> : null}
            <div className="actions">
              <button type="button" onClick={handleImport} disabled={!uploadFile || !canImport || isActionLoading}>
                {t("priceVersionPage.import.commit")}
              </button>
            </div>
          </div>
        ) : null}

        {tab === "preview" ? (
          <div className="stack">
            <div className="form-grid">
              <label className="form-field">
                <span className="label">{t("priceVersionPage.preview.search")}</span>
                <input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder={t("priceVersionPage.preview.searchPlaceholder")} />
              </label>
              <label className="form-field">
                <span className="label">{t("priceVersionPage.preview.errorsOnly")}</span>
                <input type="checkbox" checked={errorsOnly} onChange={(event) => setErrorsOnly(event.target.checked)} />
              </label>
            </div>
            {items.length === 0 ? (
              <EmptyState title={t("priceVersionPage.preview.emptyTitle")} description={t("priceVersionPage.preview.emptyDescription")} />
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>{t("priceVersionPage.preview.table.station")}</th>
                    <th>{t("priceVersionPage.preview.table.product")}</th>
                    <th>{t("priceVersionPage.preview.table.price")}</th>
                    <th>{t("priceVersionPage.preview.table.currency")}</th>
                    <th>{t("priceVersionPage.preview.table.validFrom")}</th>
                    <th>{t("priceVersionPage.preview.table.errors")}</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item, index) => (
                    <tr key={`${item.station_id ?? item.station_code ?? "row"}-${index}`}>
                      <td>{item.station_code ?? item.station_id ?? t("common.notAvailable")}</td>
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
                {t("common.back")}
              </button>
              <span className="muted">
                {t("priceVersionPage.pagination.page", {
                  current: page,
                  total: itemsTotal ? t("priceVersionPage.pagination.total", { total: Math.ceil(itemsTotal / 20) }) : "",
                })}
              </span>
              <button type="button" onClick={() => setPage(page + 1)} disabled={items.length < 20}>
                {t("common.next")}
              </button>
            </div>
          </div>
        ) : null}

        {tab === "validate" ? (
          <div className="stack">
            <button type="button" onClick={handleValidate} disabled={!canImport || isActionLoading}>
              {t("priceVersionPage.validate.run")}
            </button>
            {validation ? (
              <div className="meta-grid">
                <div>
                  <div className="label">OK</div>
                  <div>{validation.ok ? t("priceVersionPage.validate.yes") : t("priceVersionPage.validate.no")}</div>
                </div>
                <div>
                  <div className="label">{t("priceVersionPage.validate.errors")}</div>
                  <div>{validation.errors_total}</div>
                </div>
                <div>
                  <div className="label">{t("priceVersionPage.validate.warnings")}</div>
                  <div>{validation.warnings_total}</div>
                </div>
              </div>
            ) : (
              <EmptyState title={t("priceVersionPage.validate.emptyTitle")} description={t("priceVersionPage.validate.emptyDescription")} />
            )}
            {validation?.sample_errors?.length ? (
              <div>
                <h4>{t("priceVersionPage.validate.sampleErrors")}</h4>
                <ul className="bullets">
                  {validation.sample_errors.map((errorItem, index) => (
                    <li key={`${errorItem.code}-${index}`}>{errorItem.message}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {validation?.recommended_actions?.length ? (
              <div>
                <h4>{t("priceVersionPage.validate.recommendedActions")}</h4>
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
              <span className="label">{t("priceVersionPage.diff.compareTo")}</span>
              <select value={diffTarget} onChange={(event) => setDiffTarget(event.target.value)}>
                <option value="">{t("priceVersionPage.diff.selectVersion")}</option>
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
                    <div className="label">{t("priceVersionPage.diff.added")}</div>
                    <div>{diffResult.added_count}</div>
                  </div>
                  <div>
                    <div className="label">{t("priceVersionPage.diff.removed")}</div>
                    <div>{diffResult.removed_count}</div>
                  </div>
                  <div>
                    <div className="label">{t("priceVersionPage.diff.changed")}</div>
                    <div>{diffResult.changed_count}</div>
                  </div>
                </div>
                {diffResult.sample_changed?.length ? (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>{t("priceVersionPage.diff.table.station")}</th>
                        <th>{t("priceVersionPage.diff.table.product")}</th>
                        <th>{t("priceVersionPage.diff.table.before")}</th>
                        <th>{t("priceVersionPage.diff.table.after")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {diffResult.sample_changed.map((item, index) => (
                        <tr key={`${item.product_code}-${index}`}>
                          <td>{item.station_code ?? item.station_id ?? t("common.notAvailable")}</td>
                          <td>{item.product_code}</td>
                          <td>{item.before ? JSON.stringify(item.before) : t("common.notAvailable")}</td>
                          <td>{item.after ? JSON.stringify(item.after) : t("common.notAvailable")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <EmptyState title={t("priceVersionPage.diff.emptyTitle")} description={t("priceVersionPage.diff.emptyDescription")} />
                )}
              </div>
            ) : (
              <EmptyState title={t("priceVersionPage.diff.selectTitle")} description={t("priceVersionPage.diff.selectDescription")} />
            )}
          </div>
        ) : null}

        {tab === "audit" ? (
          <div className="stack">
            {auditEvents.length === 0 ? (
              <EmptyState title={t("priceVersionPage.audit.emptyTitle")} description={t("priceVersionPage.audit.emptyDescription")} />
            ) : (
              <div className="timeline-list">
                {auditEvents.map((eventItem) => (
                  <div className="timeline-item" key={eventItem.id}>
                    <div className="timeline-item__meta">
                      <span className="timeline-item__title">{eventItem.action}</span>
                      <span className="muted">{formatDateTime(eventItem.created_at)}</span>
                    </div>
                    <div className="timeline-item__body">
                      <span>{t("priceVersionPage.audit.actor", { actor: eventItem.actor ?? "system" })}</span>
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
