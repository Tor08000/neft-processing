import { useEffect, useMemo, useState } from "react";
import { fetchClientLimits, requestLimitChange } from "../api/controls";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { ConfirmActionModal } from "../components/ConfirmActionModal";
import { AppErrorState, AppForbiddenState, AppLoadingState } from "../components/states";
import type { ClientLimitItem, ClientLimitsResponse, LimitChangeRequestResponse } from "../types/controls";
import { hasAnyRole } from "../utils/roles";

interface PageErrorState {
  message: string;
  status?: number;
  correlationId?: string | null;
}

interface LimitChangeResult {
  response: LimitChangeRequestResponse;
  correlationId: string | null;
}

const formatNumber = (value?: number | null) => {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("ru-RU").format(value);
};

const limitStatusTone = (status?: string | null) => {
  switch (status) {
    case "OK":
      return "pill pill--success";
    case "NEAR_LIMIT":
      return "pill pill--warning";
    case "EXCEEDED":
      return "pill pill--danger";
    default:
      return "pill";
  }
};

const limitStatusLabel = (status?: string | null) => status ?? "—";

const buildLimitLabel = (item: ClientLimitItem) =>
  item.label ?? item.service ?? item.partner ?? item.station ?? item.type ?? "—";

const computeUsagePercent = (item: ClientLimitItem) => {
  if (item.limit === null || item.limit === undefined) return null;
  if (item.used === null || item.used === undefined) return null;
  if (item.limit <= 0) return null;
  const percent = Math.min(100, Math.round((item.used / item.limit) * 100));
  return percent;
};

export function ClientLimitsPage() {
  const { user } = useAuth();
  const [limits, setLimits] = useState<ClientLimitsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<PageErrorState | null>(null);
  const [isRequestOpen, setIsRequestOpen] = useState(false);
  const [requestType, setRequestType] = useState("");
  const [requestValue, setRequestValue] = useState("");
  const [requestComment, setRequestComment] = useState("");
  const [requestError, setRequestError] = useState<PageErrorState | null>(null);
  const [requestResult, setRequestResult] = useState<LimitChangeResult | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const canManage = hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ADMIN"]);

  const loadLimits = () => {
    if (!user) return;
    setIsLoading(true);
    setError(null);
    fetchClientLimits(user)
      .then(setLimits)
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setError({ message: err.message, status: err.status, correlationId: err.correlationId });
          return;
        }
        setError({ message: err instanceof Error ? err.message : "Не удалось загрузить лимиты" });
      })
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    loadLimits();
  }, [user]);

  const groups = useMemo(
    () => [
      { key: "amount", title: "По сумме", items: limits?.amount_limits ?? [] },
      { key: "operations", title: "По операциям", items: limits?.operation_limits ?? [] },
      { key: "services", title: "По типам услуг", items: limits?.service_limits ?? [] },
      { key: "partners", title: "По партнёрам", items: limits?.partner_limits ?? [] },
      { key: "stations", title: "По станциям", items: limits?.station_limits ?? [] },
    ],
    [limits],
  );

  const totalItems = groups.reduce((sum, group) => sum + group.items.length, 0);

  if (!user) {
    return <AppForbiddenState message="Требуется авторизация." />;
  }

  if (isLoading) {
    return <AppLoadingState label="Загружаем лимиты..." />;
  }

  if (error) {
    return (
      <AppErrorState
        message={error.message}
        status={error.status}
        correlationId={error.correlationId}
        onRetry={loadLimits}
      />
    );
  }

  const handleOpenRequest = () => {
    setIsRequestOpen(true);
    setRequestType("");
    setRequestValue("");
    setRequestComment("");
    setRequestError(null);
    setRequestResult(null);
  };

  const handleSubmitRequest = async () => {
    if (!user) return;
    const newValue = Number(requestValue);
    if (!requestType || Number.isNaN(newValue)) {
      setRequestError({ message: "Укажите корректный тип лимита и значение." });
      return;
    }
    setIsSubmitting(true);
    setRequestError(null);
    try {
      const response = await requestLimitChange(user, {
        limit_type: requestType,
        new_value: newValue,
        comment: requestComment || null,
      });
      setRequestResult({ response: response.data, correlationId: response.correlationId });
      setRequestType("");
      setRequestValue("");
      setRequestComment("");
      loadLimits();
    } catch (err) {
      if (err instanceof ApiError) {
        setRequestError({ message: err.message, status: err.status, correlationId: err.correlationId });
      } else {
        setRequestError({ message: err instanceof Error ? err.message : "Не удалось отправить запрос" });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderLimitTable = (items: ClientLimitItem[]) => {
    if (items.length === 0) {
      return <div className="muted">Лимитов пока нет.</div>;
    }

    return (
      <table className="table">
        <thead>
          <tr>
            <th>Тип</th>
            <th>Период</th>
            <th>Лимит</th>
            <th>Использовано</th>
            <th>Утилизация</th>
            <th>Статус</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, index) => {
            const usage = computeUsagePercent(item);
            return (
              <tr key={`${item.id ?? item.type ?? "limit"}-${index}`}>
                <td>{buildLimitLabel(item)}</td>
                <td>{item.period ?? "—"}</td>
                <td>{formatNumber(item.limit)}</td>
                <td>{formatNumber(item.used)}</td>
                <td>
                  {usage !== null ? (
                    <div className="stack-inline">
                      <div className="chart-bar">
                        <span className="chart-bar__fill" style={{ width: `${usage}%` }} />
                      </div>
                      <span className="muted small">{usage}%</span>
                    </div>
                  ) : (
                    "—"
                  )}
                </td>
                <td>
                  <span className={limitStatusTone(item.status)}>{limitStatusLabel(item.status)}</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    );
  };

  return (
    <div className="stack">
      <section className="card">
        <div className="card__header">
          <div>
            <h3>Лимиты</h3>
            <p className="muted">Текущие лимиты и утилизация по категориям.</p>
          </div>
          <button type="button" className="primary" onClick={handleOpenRequest} disabled={!canManage}>
            Запросить изменение лимита
          </button>
        </div>
        {!canManage ? <div className="muted small">Изменения доступны только CLIENT_OWNER/CLIENT_ADMIN.</div> : null}
        {totalItems === 0 ? <div className="muted small">Пока нет активных лимитов.</div> : null}
      </section>

      {groups.map((group) => (
        <section className="card" key={group.key}>
          <div className="section-title">
            <h4>{group.title}</h4>
          </div>
          {renderLimitTable(group.items)}
        </section>
      ))}

      <ConfirmActionModal
        isOpen={isRequestOpen}
        title="Запросить изменение лимита"
        description="Запрос будет обработан в control plane. Ответ может быть применён сразу или отправлен на согласование."
        confirmLabel="Отправить запрос"
        onConfirm={() => void handleSubmitRequest()}
        onCancel={() => setIsRequestOpen(false)}
        isProcessing={isSubmitting}
        isConfirmDisabled={!requestType || !requestValue}
        footerNote="Действие будет зафиксировано в audit-логе."
      >
        {requestResult ? (
          <div className="notice">
            <strong>Запрос отправлен</strong>
            <div className="muted small">Статус: {requestResult.response.status}</div>
            {requestResult.response.request_id ? (
              <div className="muted small">Request ID: {requestResult.response.request_id}</div>
            ) : null}
            {requestResult.correlationId ? (
              <div className="muted small">Correlation ID: {requestResult.correlationId}</div>
            ) : null}
            {requestResult.response.message ? (
              <div className="muted small">{requestResult.response.message}</div>
            ) : null}
          </div>
        ) : (
          <div className="stack">
            <label className="filter">
              Тип лимита
              <input value={requestType} onChange={(event) => setRequestType(event.target.value)} />
            </label>
            <label className="filter">
              Новое значение
              <input
                value={requestValue}
                onChange={(event) => setRequestValue(event.target.value)}
                inputMode="numeric"
              />
            </label>
            <label className="filter">
              Комментарий
              <textarea rows={3} value={requestComment} onChange={(event) => setRequestComment(event.target.value)} />
            </label>
            {requestError ? (
              <div className="notice error">
                {requestError.message}
                {requestError.correlationId ? (
                  <div className="muted small">Correlation ID: {requestError.correlationId}</div>
                ) : null}
              </div>
            ) : null}
          </div>
        )}
      </ConfirmActionModal>
    </div>
  );
}
