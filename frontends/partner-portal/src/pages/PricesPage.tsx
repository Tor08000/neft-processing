import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { fetchStations } from "../api/partner";
import { createPriceVersion, fetchPriceVersions, importPriceVersion } from "../api/prices";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ErrorState, ForbiddenState, LoadingState } from "../components/states";
import type { StationListItem } from "../api/partner";
import type { PriceVersion } from "../types/prices";
import { formatDateTime } from "../utils/format";
import { canCreateDraftPrices, canPublishPrices, canReadPrices } from "../utils/roles";
import { parseCsv } from "../utils/csv";
import { ApiError } from "../api/http";
import { StatusBadge } from "../components/StatusBadge";

const statusLabels: Record<string, string> = {
  DRAFT: "Draft",
  VALIDATED: "Validated",
  PUBLISHED: "Published",
  ARCHIVED: "Archived",
};

const shortId = (value: string) => value.slice(0, 8);

export function PricesPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
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
          setError(err instanceof ApiError ? err : new ApiError("Не удалось загрузить версии цен", 500, null));
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

  const activeVersion = useMemo(() => versions.find((version) => version.active), [versions]);
  const lastPublished = useMemo(
    () => versions.filter((version) => version.status === "PUBLISHED").sort((a, b) => b.created_at.localeCompare(a.created_at))[0],
    [versions],
  );
  const draftCount = useMemo(() => versions.filter((version) => version.status === "DRAFT").length, [versions]);

  const handleCreateDraft = async () => {
    if (!user || !canCreateDraft) return;
    if (!window.confirm("Создать черновик версии цен?")) return;
    setActionMessage(null);
    setActionCorrelation(null);
    try {
      const response = await createPriceVersion(user.token, { station_scope: stationFilter ? "list" : "all", station_ids: stationFilter ? [stationFilter] : undefined });
      setActionMessage("Черновик создан");
      setActionCorrelation(response.correlationId);
      navigate(`/prices/${response.data.id}`);
    } catch (err) {
      console.error(err);
      if (err instanceof ApiError) {
        setActionMessage(`Ошибка: ${err.message} (status ${err.status})`);
        setActionCorrelation(err.correlationId);
      } else {
        setActionMessage("Не удалось создать черновик");
      }
    }
  };

  const handleUpload = async () => {
    if (!user || !draftSelection || !uploadFile) return;
    if (!window.confirm("Импортировать файл в черновик?")) return;
    setIsUploading(true);
    setActionMessage(null);
    setActionCorrelation(null);
    try {
      const content = await uploadFile.arrayBuffer();
      const base64 = btoa(String.fromCharCode(...new Uint8Array(content)));
      const response = await importPriceVersion(user.token, draftSelection, { format: uploadFormat, content_base64: base64 });
      setActionMessage(`Импорт завершён. Ошибок: ${response.data.errors_found}`);
      setActionCorrelation(response.correlationId);
      setUploadFile(null);
      setDraftSelection("");
    } catch (err) {
      console.error(err);
      if (err instanceof ApiError) {
        setActionMessage(`Ошибка: ${err.message} (status ${err.status})`);
        setActionCorrelation(err.correlationId);
      } else {
        setActionMessage("Не удалось импортировать файл");
      }
    } finally {
      setIsUploading(false);
    }
  };

  if (!canRead) {
    return <ForbiddenState description="Роль не позволяет просматривать версии цен." />;
  }

  if (isLoading) {
    return <LoadingState label="Загружаем версии цен..." />;
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

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <div>
            <h2>Цены</h2>
            <p className="muted">Управление версиями прайс-листов партнёра.</p>
          </div>
          <button type="button" className="primary" onClick={handleCreateDraft} disabled={!canCreateDraft}>
            Создать черновик
          </button>
        </div>
        <div className="form-grid">
          <label className="form-field">
            <span className="label">Станция</span>
            <select value={stationFilter} onChange={(event) => setStationFilter(event.target.value)}>
              <option value="">Все станции</option>
              {stations.map((station) => (
                <option key={station.id} value={station.id}>
                  {station.name}
                </option>
              ))}
            </select>
          </label>
          <label className="form-field">
            <span className="label">Статус</span>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">Все</option>
              {Object.keys(statusLabels).map((status) => (
                <option key={status} value={status}>
                  {statusLabels[status]}
                </option>
              ))}
            </select>
          </label>
          <label className="form-field">
            <span className="label">Дата от</span>
            <input type="date" value={fromFilter} onChange={(event) => setFromFilter(event.target.value)} />
          </label>
          <label className="form-field">
            <span className="label">Дата до</span>
            <input type="date" value={toFilter} onChange={(event) => setToFilter(event.target.value)} />
          </label>
        </div>
      </section>

      <section className="card">
        <h3>Quick insights</h3>
        <div className="meta-grid">
          <div>
            <div className="label">Активная версия</div>
            <div>{activeVersion ? shortId(activeVersion.id) : "—"}</div>
          </div>
          <div>
            <div className="label">Последняя публикация</div>
            <div>{lastPublished ? formatDateTime(lastPublished.created_at) : "—"}</div>
          </div>
          <div>
            <div className="label">Черновики к проверке</div>
            <div>{draftCount}</div>
          </div>
        </div>
      </section>

      <section className="card">
        <h3>Импорт в черновик</h3>
        <div className="form-grid">
          <label className="form-field">
            <span className="label">Выберите черновик</span>
            <select value={draftSelection} onChange={(event) => setDraftSelection(event.target.value)}>
              <option value="">Не выбран</option>
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
          <button type="button" onClick={handleUpload} disabled={!draftSelection || !uploadFile || isUploading}>
            {isUploading ? "Импортируем..." : "Загрузить в черновик"}
          </button>
        </div>
      </section>

      {actionMessage ? (
        <section className="card">
          <div className="notice">
            <strong>{actionMessage}</strong>
            {actionCorrelation ? <div className="muted">Correlation ID: {actionCorrelation}</div> : null}
          </div>
        </section>
      ) : null}

      <section className="card">
        <h3>Версии прайс-листов</h3>
        {versions.length === 0 ? (
          <EmptyState
            title="Версий прайс-листов пока нет"
            description="Создайте черновик или импортируйте файл, чтобы начать работу."
            action={
              <button type="button" className="ghost" onClick={handleCreateDraft} disabled={!canCreateDraft}>
                Создать черновик
              </button>
            }
          />
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Версия</th>
                <th>Статус</th>
                <th>Scope</th>
                <th>Создана</th>
                <th>Items</th>
                <th>Errors</th>
                <th>Active</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {versions.map((version) => (
                <tr key={version.id}>
                  <td>{shortId(version.id)}</td>
                  <td>
                    <StatusBadge status={version.status.toLowerCase()} />
                  </td>
                  <td>{version.station_scope === "all" ? "Все станции" : `${version.station_ids?.length ?? 0} станций`}</td>
                  <td>{formatDateTime(version.created_at)}</td>
                  <td>{version.item_count}</td>
                  <td>{version.error_count}</td>
                  <td>{version.active ? "Активная" : "—"}</td>
                  <td>
                    <div className="actions">
                      <Link className="ghost" to={`/prices/${version.id}`}>
                        открыть
                      </Link>
                      {version.status === "VALIDATED" && canPublish ? (
                        <Link className="ghost" to={`/prices/${version.id}?action=publish`}>
                          publish
                        </Link>
                      ) : null}
                      {version.status === "PUBLISHED" && canPublish ? (
                        <Link className="ghost" to={`/prices/${version.id}?action=rollback`}>
                          rollback
                        </Link>
                      ) : null}
                      <Link className="ghost" to={`/prices/${version.id}?tab=diff`}>
                        diff
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
