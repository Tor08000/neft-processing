import { useEffect, useState } from "react";
import { fetchClientServices, toggleClientService } from "../api/controls";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { ConfirmActionModal } from "../components/ConfirmActionModal";
import { AppEmptyState, AppErrorState, AppForbiddenState, AppLoadingState } from "../components/states";
import type { ClientServiceItem, ControlToggleResponse } from "../types/controls";
import { hasAnyRole } from "../utils/roles";

interface PageErrorState {
  message: string;
  status?: number;
  correlationId?: string | null;
}

interface ToggleNotice {
  item: ClientServiceItem;
  response: ControlToggleResponse;
  correlationId: string | null;
}

const statusTone = (status?: string | null) => {
  switch (status) {
    case "ENABLED":
      return "pill pill--success";
    case "DISABLED":
      return "pill pill--danger";
    default:
      return "pill";
  }
};

export function ClientServicesPage() {
  const { user } = useAuth();
  const [services, setServices] = useState<ClientServiceItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<PageErrorState | null>(null);
  const [toggleItem, setToggleItem] = useState<ClientServiceItem | null>(null);
  const [toggleNotice, setToggleNotice] = useState<ToggleNotice | null>(null);
  const [toggleError, setToggleError] = useState<PageErrorState | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const canManage = hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ADMIN"]);

  const loadServices = () => {
    if (!user) return;
    setIsLoading(true);
    setError(null);
    fetchClientServices(user)
      .then((resp) => setServices(resp.items ?? []))
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setError({ message: err.message, status: err.status, correlationId: err.correlationId });
          return;
        }
        setError({ message: err instanceof Error ? err.message : "Не удалось загрузить услуги" });
      })
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    loadServices();
  }, [user]);

  if (!user) {
    return <AppForbiddenState message="Требуется авторизация." />;
  }

  if (isLoading) {
    return <AppLoadingState label="Загружаем услуги..." />;
  }

  if (error) {
    return (
      <AppErrorState
        message={error.message}
        status={error.status}
        correlationId={error.correlationId}
        onRetry={loadServices}
      />
    );
  }

  const handleToggle = async () => {
    if (!user || !toggleItem) return;
    setIsSubmitting(true);
    setToggleError(null);
    try {
      const response = await toggleClientService(user, toggleItem.id);
      setToggleNotice({ item: toggleItem, response: response.data, correlationId: response.correlationId });
      setToggleItem(null);
      loadServices();
    } catch (err) {
      if (err instanceof ApiError) {
        setToggleError({ message: err.message, status: err.status, correlationId: err.correlationId });
      } else {
        setToggleError({ message: err instanceof Error ? err.message : "Не удалось изменить доступ" });
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
            <h3>Услуги и партнёры</h3>
            <p className="muted">Включайте или отключайте доступ к услугам и партнёрам.</p>
          </div>
        </div>
        {toggleNotice ? (
          <div className="notice">
            <strong>Ответ control plane получен</strong>
            <div className="muted small">
              {toggleNotice.item.partner ?? "Партнёр"} · {toggleNotice.item.service ?? "Партнёр целиком"}
            </div>
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
        {services.length === 0 ? (
          <AppEmptyState title="Услуги не найдены" description="Нет подключённых услуг для управления." />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Партнёр</th>
                <th>Услуга</th>
                <th>Статус</th>
                <th>Ограничения</th>
                <th>Действие</th>
              </tr>
            </thead>
            <tbody>
              {services.map((item) => {
                const actionLabel = item.status === "ENABLED" ? "Отключить" : "Включить";
                return (
                  <tr key={item.id}>
                    <td>{item.partner ?? "—"}</td>
                    <td>{item.service ?? "Партнёр целиком"}</td>
                    <td>
                      <span className={statusTone(item.status)}>{item.status ?? "—"}</span>
                    </td>
                    <td>{item.restrictions ?? "—"}</td>
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
        title="Изменить доступ"
        description={
          toggleItem
            ? `${toggleItem.partner ?? "Партнёр"} · ${toggleItem.service ?? "Партнёр целиком"}`
            : undefined
        }
        confirmLabel={toggleItem?.status === "ENABLED" ? "Отключить" : "Включить"}
        onConfirm={() => void handleToggle()}
        onCancel={() => setToggleItem(null)}
        isProcessing={isSubmitting}
        isConfirmDisabled={!toggleItem}
        footerNote="Действие будет зафиксировано в audit-логе."
      >
        <div className="muted">Подтвердите изменение доступа. Результат зависит от проверок backend.</div>
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
