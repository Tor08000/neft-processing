import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { BadgeDollarSign } from "../components/icons";
import { fetchStations } from "../api/partner";
import { createPriceVersion, fetchPriceVersions, importPriceVersion } from "../api/prices";
import { useAuth } from "../auth/AuthContext";
import { EmptyState } from "../components/EmptyState";
import { ErrorState, ForbiddenState, LoadingState } from "../components/states";
import type { StationListItem } from "../api/partner";
import type { PriceVersion } from "../types/prices";
import { formatDateTime } from "../utils/format";
import { canCreateDraftPrices, canPublishPrices, canReadPrices } from "../utils/roles";
import { parseCsv } from "../utils/csv";
import { ApiError } from "../api/http";
import { StatusBadge } from "../components/StatusBadge";
import { useI18n } from "../i18n";

const shortId = (value: string) => value.slice(0, 8);

export function PricesPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { t } = useI18n();
  const [versions, setVersions] = useState<PriceVersion[]>([]);
  const [stations, setStations] = useState<StationListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [stationFilter, setStationFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [fromFilter, setFromFilter] = useState("");
  const [toFilter, setToFilter] = useState("");
  const [draftSelection, setDraftSelection] = useState("");
  const [uploadFormat, setUploadFormat] = useState<"CSV" | "JSON">("CSV");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadPreview, setUploadPreview] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionCorrelation, setActionCorrelation] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const canRead = canReadPrices(user?.roles);
  const canCreateDraft = canCreateDraftPrices(user?.roles);
  const canPublish = canPublishPrices(user?.roles);
  const statusLabels = useMemo(
    () => ({
      DRAFT: t("pricesPage.statuses.draft"),
      VALIDATED: t("pricesPage.statuses.validated"),
      PUBLISHED: t("pricesPage.statuses.published"),
      ARCHIVED: t("pricesPage.statuses.archived"),
    }),
    [t],
  );

  useEffect(() => {
    let active = true;
    if (!user || !canRead) return;
    setIsLoading(true);
    Promise.all([fetchPriceVersions(user.token, { station_id: stationFilter, status: statusFilter, from: fromFilter, to: toFilter }), fetchStations(user.token)])
      .then(([versionsResponse, stationsResponse]) => {
        if (!active) return;
        setVersions(versionsResponse.items ?? []);
        setStations(stationsResponse.items ?? []);
        setError(null);
      })
      .catch((err) => {
        console.error(err);
        if (active) {
          setError(err instanceof ApiError ? err : new ApiError(t("pricesPage.errors.loadFailed"), 500, null));
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
  }, [user, stationFilter, statusFilter, fromFilter, toFilter, canRead]);

  useEffect(() => {
    if (!uploadFile) {
      setUploadPreview(null);
      return;
    }
    if (uploadFormat === "CSV") {
      uploadFile.text().then((text) => {
        const result = parseCsv(text);
        if (result.errors.length) {
          setUploadPreview(t("pricesPage.upload.csvErrors", { count: result.errors.length }));
        } else {
          setUploadPreview(t("pricesPage.upload.csvRows", { count: result.rows.length }));
        }
      });
    } else {
      uploadFile.text().then((text) => {
        try {
          const parsed = JSON.parse(text) as unknown;
          const rowsCount = Array.isArray(parsed) ? parsed.length : 0;
          setUploadPreview(t("pricesPage.upload.jsonRows", { count: rowsCount }));
        } catch (err) {
          setUploadPreview(t("pricesPage.upload.jsonError"));
        }
      });
    }
  }, [uploadFile, uploadFormat]);

  const activeVersion = useMemo(() => versions.find((version) => version.active), [versions]);
  const lastPublished = useMemo(
    () => versions.filter((version) => version.status === "PUBLISHED").sort((a, b) => b.created_at.localeCompare(a.created_at))[0],
    [versions],
  );
  const draftCount = useMemo(() => versions.filter((version) => version.status === "DRAFT").length, [versions]);

  const handleCreateDraft = async () => {
    if (!user || !canCreateDraft) return;
    if (!window.confirm(t("pricesPage.confirmations.createDraft"))) return;
    setActionMessage(null);
    setActionCorrelation(null);
    try {
      const response = await createPriceVersion(user.token, { station_scope: stationFilter ? "list" : "all", station_ids: stationFilter ? [stationFilter] : undefined });
      setActionMessage(t("pricesPage.notifications.draftCreated"));
      setActionCorrelation(response.correlationId);
      navigate(`/prices/${response.data.id}`);
    } catch (err) {
      console.error(err);
      if (err instanceof ApiError) {
        setActionMessage(t("pricesPage.errors.apiError", { message: err.message, status: err.status }));
        setActionCorrelation(err.correlationId);
      } else {
        setActionMessage(t("pricesPage.errors.createDraftFailed"));
      }
    }
  };

  const handleUpload = async () => {
    if (!user || !draftSelection || !uploadFile) return;
    if (!window.confirm(t("pricesPage.confirmations.importDraft"))) return;
    setIsUploading(true);
    setActionMessage(null);
    setActionCorrelation(null);
    try {
      const content = await uploadFile.arrayBuffer();
      const base64 = btoa(String.fromCharCode(...new Uint8Array(content)));
      const response = await importPriceVersion(user.token, draftSelection, { format: uploadFormat, content_base64: base64 });
      setActionMessage(t("pricesPage.notifications.importCompleted", { errors: response.data.errors_found }));
      setActionCorrelation(response.correlationId);
      setUploadFile(null);
      setDraftSelection("");
    } catch (err) {
      console.error(err);
      if (err instanceof ApiError) {
        setActionMessage(t("pricesPage.errors.apiError", { message: err.message, status: err.status }));
        setActionCorrelation(err.correlationId);
      } else {
        setActionMessage(t("pricesPage.errors.importFailed"));
      }
    } finally {
      setIsUploading(false);
    }
  };

  if (!canRead) {
    return <ForbiddenState description={t("pricesPage.forbidden.noAccess")} />;
  }

  if (isLoading) {
    return <LoadingState label={t("pricesPage.loading")} />;
  }

  if (error) {
    return (
      <ErrorState
        title={t("pricesPage.errors.loadTitle", { status: error.status })}
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

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <div>
            <h2>{t("pricesPage.title")}</h2>
            <p className="muted">{t("pricesPage.subtitle")}</p>
          </div>
          <button type="button" className="primary" onClick={handleCreateDraft} disabled={!canCreateDraft}>
            {t("actions.createDraft")}
          </button>
        </div>
        <div className="form-grid">
          <label className="form-field">
            <span className="label">{t("pricesPage.filters.station")}</span>
            <select value={stationFilter} onChange={(event) => setStationFilter(event.target.value)}>
              <option value="">{t("pricesPage.filters.allStations")}</option>
              {stations.map((station) => (
                <option key={station.id} value={station.id}>
                  {station.name}
                </option>
              ))}
            </select>
          </label>
          <label className="form-field">
            <span className="label">{t("pricesPage.filters.status")}</span>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">{t("common.all")}</option>
              {Object.keys(statusLabels).map((status) => (
                <option key={status} value={status}>
                  {statusLabels[status]}
                </option>
              ))}
            </select>
          </label>
          <label className="form-field">
            <span className="label">{t("pricesPage.filters.from")}</span>
            <input type="date" value={fromFilter} onChange={(event) => setFromFilter(event.target.value)} />
          </label>
          <label className="form-field">
            <span className="label">{t("pricesPage.filters.to")}</span>
            <input type="date" value={toFilter} onChange={(event) => setToFilter(event.target.value)} />
          </label>
        </div>
      </section>

      <section className="card">
        <h3>{t("pricesPage.insights.title")}</h3>
        <div className="meta-grid">
          <div>
            <div className="label">{t("pricesPage.insights.activeVersion")}</div>
            <div>{activeVersion ? shortId(activeVersion.id) : t("common.notAvailable")}</div>
          </div>
          <div>
            <div className="label">{t("pricesPage.insights.lastPublished")}</div>
            <div>{lastPublished ? formatDateTime(lastPublished.created_at) : t("common.notAvailable")}</div>
          </div>
          <div>
            <div className="label">{t("pricesPage.insights.drafts")}</div>
            <div>{draftCount}</div>
          </div>
        </div>
      </section>

      <section className="card">
        <h3>{t("pricesPage.upload.title")}</h3>
        <div className="form-grid">
          <label className="form-field">
            <span className="label">{t("pricesPage.upload.selectDraft")}</span>
            <select value={draftSelection} onChange={(event) => setDraftSelection(event.target.value)}>
              <option value="">{t("pricesPage.upload.notSelected")}</option>
              {versions
                .filter((version) => version.status === "DRAFT")
                .map((version) => (
                  <option key={version.id} value={version.id}>
                    {shortId(version.id)}
                  </option>
                ))}
            </select>
          </label>
          <label className="form-field">
            <span className="label">{t("pricesPage.upload.format")}</span>
            <select value={uploadFormat} onChange={(event) => setUploadFormat(event.target.value as "CSV" | "JSON")}>
              <option value="CSV">{t("pricesPage.upload.formats.csv")}</option>
              <option value="JSON">{t("pricesPage.upload.formats.json")}</option>
            </select>
          </label>
          <label className="form-field form-grid__full">
            <span className="label">{t("pricesPage.upload.file")}</span>
            <input type="file" accept={uploadFormat === "CSV" ? ".csv" : ".json,application/json"} onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)} />
          </label>
        </div>
        {uploadPreview ? <p className="muted">{t("pricesPage.upload.preview", { text: uploadPreview })}</p> : null}
        <div className="actions">
          <button type="button" onClick={handleUpload} disabled={!draftSelection || !uploadFile || isUploading}>
            {isUploading ? t("pricesPage.upload.loading") : t("pricesPage.upload.submit")}
          </button>
        </div>
      </section>

      {actionMessage ? (
        <section className="card">
          <div className="notice">
            <strong>{actionMessage}</strong>
            {actionCorrelation ? <div className="muted">{t("errors.correlationId", { id: actionCorrelation })}</div> : null}
          </div>
        </section>
      ) : null}

      <section className="card">
        <h3>{t("pricesPage.versions.title")}</h3>
        {versions.length === 0 ? (
          <EmptyState
            icon={<BadgeDollarSign />}
            title={t("emptyStates.prices.title")}
            description={t("emptyStates.prices.description")}
            primaryAction={{
              label: t("actions.createDraft"),
              onClick: handleCreateDraft,
              variant: "ghost",
            }}
          />
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>{t("pricesPage.versions.table.version")}</th>
                <th>{t("common.status")}</th>
                <th>{t("pricesPage.versions.table.scope")}</th>
                <th>{t("pricesPage.versions.table.createdAt")}</th>
                <th>{t("pricesPage.versions.table.items")}</th>
                <th>{t("pricesPage.versions.table.errors")}</th>
                <th>{t("pricesPage.versions.table.active")}</th>
                <th>{t("common.actions")}</th>
              </tr>
            </thead>
            <tbody>
              {versions.map((version) => (
                <tr key={version.id}>
                  <td>{shortId(version.id)}</td>
                  <td>
                    <StatusBadge status={version.status.toLowerCase()} />
                  </td>
                  <td>
                    {version.station_scope === "all"
                      ? t("pricesPage.versions.scopeAll")
                      : t("pricesPage.versions.scopeCount", { count: version.station_ids?.length ?? 0 })}
                  </td>
                  <td>{formatDateTime(version.created_at)}</td>
                  <td>{version.item_count}</td>
                  <td>{version.error_count}</td>
                  <td>{version.active ? t("pricesPage.versions.active") : t("common.notAvailable")}</td>
                  <td>
                    <div className="actions">
                      <Link className="ghost" to={`/prices/${version.id}`}>
                        {t("common.open")}
                      </Link>
                      {version.status === "VALIDATED" && canPublish ? (
                        <Link className="ghost" to={`/prices/${version.id}?action=publish`}>
                          {t("pricesPage.versions.actions.publish")}
                        </Link>
                      ) : null}
                      {version.status === "PUBLISHED" && canPublish ? (
                        <Link className="ghost" to={`/prices/${version.id}?action=rollback`}>
                          {t("pricesPage.versions.actions.rollback")}
                        </Link>
                      ) : null}
                      <Link className="ghost" to={`/prices/${version.id}?tab=diff`}>
                        {t("pricesPage.versions.actions.diff")}
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
