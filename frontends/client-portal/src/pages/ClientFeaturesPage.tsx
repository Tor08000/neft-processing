import { useEffect, useState } from "react";
import { fetchClientFeatures, toggleClientFeature } from "../api/controls";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { ConfirmActionModal } from "../components/ConfirmActionModal";
import { AppEmptyState, AppErrorState, AppForbiddenState, AppLoadingState } from "../components/states";
import type { ClientFeatureItem, ControlToggleResponse } from "../types/controls";
import { hasAnyRole } from "../utils/roles";

interface PageErrorState {
  message: string;
  status?: number;
  correlationId?: string | null;
}

interface ToggleNotice {
  item: ClientFeatureItem;
  response: ControlToggleResponse;
  correlationId: string | null;
}

const statusTone = (status?: string | null) => {
  switch (status) {
    case "ON":
      return "pill pill--success";
    case "OFF":
      return "pill pill--danger";
    case "WAITING":
      return "pill pill--warning";
    default:
      return "pill";
  }
};

export function ClientFeaturesPage() {
  const { user } = useAuth();
  const [features, setFeatures] = useState<ClientFeatureItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<PageErrorState | null>(null);
  const [toggleItem, setToggleItem] = useState<ClientFeatureItem | null>(null);
  const [toggleNotice, setToggleNotice] = useState<ToggleNotice | null>(null);
  const [toggleError, setToggleError] = useState<PageErrorState | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const canManage = hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ADMIN"]);

  const loadFeatures = () => {
    if (!user) return;
    setIsLoading(true);
    setError(null);
    fetchClientFeatures(user)
      .then((resp) => setFeatures(resp.items ?? []))
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setError({ message: err.message, status: err.status, correlationId: err.correlationId });
          return;
        }
        setError({ message: err instanceof Error ? err.message : "Не удалось загрузить возможности" });
      })
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    loadFeatures();
  }, [user]);

  if (!user) {
    return <AppForbiddenState message="Требуется авторизация." />;
  }

  if (isLoading) {
    return <AppLoadingState label="Загружаем возможности..." />;
  }

  if (error) {
    return (
      <AppErrorState
        message={error.message}
        status={error.status}
        correlationId={error.correlationId}
        onRetry={loadFeatures}
      />
    );
  }

  const handleToggle = async () => {
    if (!user || !toggleItem) return;
    setIsSubmitting(true);
    setToggleError(null);
    try {
      const response = await toggleClientFeature(user, toggleItem.key);
      setToggleNotice({ item: toggleItem, response: response.data, correlationId: response.correlationId });
      setToggleItem(null);
      loadFeatures();
    } catch (err) {
      if (err instanceof ApiError) {
        setToggleError({ message: err.message, status: err.status, correlationId: err.correlationId });
      } else {
        setToggleError({ message: err instanceof Error ? err.message : "Не удалось изменить возможность" });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="stack">
      <section className="card">
        <div className="card__header">
          <div>
            <h3>Возможности</h3>
            <p className="muted">Feature toggles на уровне клиента.</p>
          </div>
        </div>
        {toggleNotice ? (
          <div className="notice">
            <strong>Ответ control plane получен</strong>
            <div className="muted small">{toggleNotice.item.key}</div>
            {toggleNotice.response.status ? (
              <div className="muted small">Статус: {toggleNotice.response.status}</div>
            ) : null}
            {toggleNotice.response.reason ? <div className="muted small">Причина: {toggleNotice.response.reason}</div> : null}
            {toggleNotice.correlationId ? (
              <div className="muted small">Correlation ID: {toggleNotice.correlationId}</div>
            ) : null}
          </div>
        ) : null}
      </section>

      <section className="card">
        {features.length === 0 ? (
          <AppEmptyState title="Возможностей нет" description="Доступные feature toggles появятся позже." />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Feature key</th>
                <th>Описание</th>
                <th>Статус</th>
                <th>Scope</th>
                <th>Действие</th>
              </tr>
            </thead>
            <tbody>
              {features.map((item) => {
                const actionLabel = item.status === "ON" ? "Отключить" : "Включить";
                return (
                  <tr key={item.key}>
                    <td>{item.key}</td>
                    <td>{item.description ?? "—"}</td>
                    <td>
                      <span className={statusTone(item.status)}>{item.status ?? "—"}</span>
                    </td>
                    <td>{item.scope ?? "client"}</td>
                    <td>
                      <button
                        type="button"
                        className="secondary"
                        disabled={!canManage}
                        onClick={() => {
                          setToggleItem(item);
                          setToggleError(null);
                        }}
                      >
                        {actionLabel}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

      <ConfirmActionModal
        isOpen={Boolean(toggleItem)}
        title="Изменить возможность"
        description={toggleItem ? toggleItem.key : undefined}
        confirmLabel={toggleItem?.status === "ON" ? "Отключить" : "Включить"}
        onConfirm={() => void handleToggle()}
        onCancel={() => setToggleItem(null)}
        isProcessing={isSubmitting}
        isConfirmDisabled={!toggleItem}
        footerNote="Действие будет зафиксировано в audit-логе."
      >
        <div className="muted">Backend может отказать или применить изменение после проверки.</div>
        {toggleError ? (
          <div className="notice error">
            {toggleError.message}
            {toggleError.correlationId ? (
              <div className="muted small">Correlation ID: {toggleError.correlationId}</div>
            ) : null}
          </div>
        ) : null}
      </ConfirmActionModal>
    </div>
  );
}
