import { useMemo } from "react";
import { Link } from "react-router-dom";
import type { ClientDashboardSnapshot } from "../api/clientPortal";
import { useAuth } from "../auth/AuthContext";
import { useClient } from "../auth/ClientContext";
import { AppEmptyState, AppErrorState, AppLoadingState } from "../components/states";
import { formatDateTime } from "../utils/format";
import { hasAnyRole } from "../utils/roles";

export function DashboardPage() {
  const { user } = useAuth();
  const { client, isLoading, error } = useClient();
  const summary = useMemo<ClientDashboardSnapshot | null>(() => client?.dashboard ?? null, [client]);

  if (!user) {
    return null;
  }

  const roles = client?.membership.roles ?? [];
  const canViewCards = hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_FLEET_MANAGER", "CLIENT_USER"]);
  const canManageCards = hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_FLEET_MANAGER"]);
  const canViewUsers = hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ADMIN"]);
  const canReadUsers = hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_ACCOUNTANT"]);
  const canViewDocuments = hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_ACCOUNTANT"]);
  const canViewActivity = hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ADMIN"]);
  const isDriver = hasAnyRole(user, ["CLIENT_USER"]);
  const isDriverOnly =
    isDriver &&
    !hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ADMIN", "CLIENT_ACCOUNTANT", "CLIENT_FLEET_MANAGER"]);
  const canViewCompanyStatus = !isDriverOnly;

  const cards = summary?.cards ?? null;
  const users = summary?.users ?? null;
  const documents = summary?.documents ?? null;
  const activity = summary?.activity ?? null;

  const planCode = client?.subscription?.plan_code ?? "—";
  const limits = client?.subscription?.limits ?? client?.entitlements.limits ?? {};
  const cardsLimit = limits.cards as { used?: number | null; max?: number | null } | undefined;
  const usersLimit = limits.users as { used?: number | null; max?: number | null } | undefined;
  const cardsLimitLabel = cardsLimit ? `${cardsLimit.used ?? 0} / ${cardsLimit.max ?? "∞"}` : "—";
  const usersLimitLabel = usersLimit ? `${usersLimit.used ?? 0} / ${usersLimit.max ?? "∞"}` : "—";
  const cardsAvailable = cards?.available_to_issue ?? null;
  const orgStatus = client?.org_status ?? "—";

  const statusCta = (() => {
    if (client?.org_status === "ONBOARDING" || !client?.org) {
      return { label: "Завершить подключение", to: "/client/onboarding" };
    }
    if (client?.org_status === "SUSPENDED") return { label: "Связаться с поддержкой", to: "/client/support" };
    return { label: "Перейти к управлению", to: "/cards" };
  })();

  return (
    <div className="stack" aria-live="polite">
      {canViewCompanyStatus ? (
        <section className="card">
          <div className="card__header">
            <div>
              <h2>Состояние компании</h2>
              <p className="muted">Статус организации и подписки.</p>
            </div>
            <Link className="ghost" to={statusCta.to}>
              {statusCta.label}
            </Link>
          </div>
          {isLoading ? <AppLoadingState label="Загружаем данные компании" /> : null}
          {error ? <AppErrorState message={error} /> : null}
          {!isLoading && !error ? (
            <div className="kpi-grid">
              <div className="kpi-card">
                <div className="kpi-card__title">Статус</div>
                <div className="kpi-card__value">{orgStatus}</div>
              </div>
              <div className="kpi-card">
                <div className="kpi-card__title">Подписка</div>
                <div className="kpi-card__value">{planCode}</div>
                <div className="muted small">Роли: {roles.length ? roles.join(", ") : "—"}</div>
              </div>
              <div className="kpi-card">
                <div className="kpi-card__title">Лимит карт</div>
                <div className="kpi-card__value">{cardsLimitLabel}</div>
                <div className="muted small">Использовано / максимум</div>
              </div>
              <div className="kpi-card">
                <div className="kpi-card__title">Лимит пользователей</div>
                <div className="kpi-card__value">{usersLimitLabel}</div>
                <div className="muted small">Использовано / максимум</div>
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      {canViewCards ? (
        <section className="card">
          <div className="card__header">
            <div>
              <h2>{isDriver ? "Мои карты" : "Карты"}</h2>
              <p className="muted">Сводка по картам компании.</p>
            </div>
            <div className="actions">
              <Link className="ghost" to="/cards">
                Перейти к картам
              </Link>
              {canManageCards && (cardsAvailable === null || cardsAvailable > 0) ? (
                <Link className="neft-button neft-btn-primary" to="/cards">
                  Выпустить карту
                </Link>
              ) : null}
            </div>
          </div>
          {isLoading ? <AppLoadingState label="Загружаем карточки" /> : null}
          {!isLoading && !error ? (
            <div className="kpi-grid">
              <div className="kpi-card">
                <div className="kpi-card__title">Всего</div>
                <div className="kpi-card__value">{cards?.total ?? 0}</div>
              </div>
              {isDriver ? (
                <div className="kpi-card">
                  <div className="kpi-card__title">Мои карты</div>
                  <div className="kpi-card__value">{cards?.mine ?? 0}</div>
                </div>
              ) : (
                <>
                  <div className="kpi-card">
                    <div className="kpi-card__title">Активные</div>
                    <div className="kpi-card__value">{cards?.active ?? 0}</div>
                  </div>
                  <div className="kpi-card">
                    <div className="kpi-card__title">Заблокированные</div>
                    <div className="kpi-card__value">{cards?.blocked ?? 0}</div>
                  </div>
                </>
              )}
            </div>
          ) : null}
          {!isLoading && !error && !cards ? (
            <AppEmptyState
              description="У вас пока нет карт. Выпустите первую карту."
              action={
                canManageCards ? (
                  <Link className="neft-button neft-btn-primary" to="/cards">
                    Выпустить первую
                  </Link>
                ) : null
              }
            />
          ) : null}
        </section>
      ) : null}

      {canViewUsers || canReadUsers ? (
        <section className="card">
          <div className="card__header">
            <div>
              <h2>Пользователи</h2>
              <p className="muted">Статусы и приглашения.</p>
            </div>
            {canViewUsers ? (
              <div className="actions">
                <Link className="ghost" to="/settings/management">
                  Управление пользователями
                </Link>
                <Link className="neft-button neft-btn-primary" to="/settings/management">
                  Пригласить сотрудника
                </Link>
              </div>
            ) : null}
          </div>
          {isLoading ? <AppLoadingState label="Загружаем пользователей" /> : null}
          {!isLoading && !error ? (
            <div className="kpi-grid">
              <div className="kpi-card">
                <div className="kpi-card__title">Всего</div>
                <div className="kpi-card__value">{users?.total ?? 0}</div>
              </div>
              <div className="kpi-card">
                <div className="kpi-card__title">Активные</div>
                <div className="kpi-card__value">{users?.active ?? 0}</div>
              </div>
              <div className="kpi-card">
                <div className="kpi-card__title">Приглашены</div>
                <div className="kpi-card__value">{users?.invited ?? 0}</div>
              </div>
              <div className="kpi-card">
                <div className="kpi-card__title">Отключены</div>
                <div className="kpi-card__value">{users?.disabled ?? 0}</div>
              </div>
            </div>
          ) : null}
          {!isLoading && !error && !users ? (
            <AppEmptyState
              description="Пока нет сотрудников в организации."
              action={
                canViewUsers ? (
                  <Link className="neft-button neft-btn-primary" to="/settings/management">
                    Пригласить первого
                  </Link>
                ) : null
              }
            />
          ) : null}
        </section>
      ) : null}

      {canViewDocuments ? (
        <section className="card">
          <div className="card__header">
            <div>
              <h2>Документы</h2>
              <p className="muted">Последние документы компании.</p>
            </div>
            <Link className="ghost" to="/client/documents">
              Все документы
            </Link>
          </div>
          {isLoading ? <AppLoadingState label="Загружаем документы" /> : null}
          {!isLoading && !error && documents?.length ? (
            <ul className="stack">
              {documents.slice(0, 5).map((doc) => (
                <li key={doc.id} className="card">
                  <div className="card__header">
                    <div>
                      <div className="kpi-card__title">{doc.type}</div>
                      <div className="muted small">{formatDateTime(doc.date)}</div>
                    </div>
                    <div className="muted">{doc.status}</div>
                  </div>
                </li>
              ))}
            </ul>
          ) : null}
          {!isLoading && !error && (!documents || documents.length === 0) ? (
            <AppEmptyState description="Нет документов. Они появятся автоматически." />
          ) : null}
        </section>
      ) : null}

      {canViewActivity ? (
        <section className="card">
          <div className="card__header">
            <div>
              <h2>Последние действия</h2>
              <p className="muted">5–10 последних событий.</p>
            </div>
            <Link className="ghost" to="/cases">
              Открыть журнал действий
            </Link>
          </div>
          {isLoading ? <AppLoadingState label="Загружаем активность" /> : null}
          {!isLoading && !error && activity?.length ? (
            <ul className="stack">
              {activity.slice(0, 10).map((event) => (
                <li key={event.id} className="card">
                  <div>{event.message}</div>
                  <div className="muted small">{formatDateTime(event.created_at)}</div>
                </li>
              ))}
            </ul>
          ) : null}
          {!isLoading && !error && (!activity || activity.length === 0) ? (
            <AppEmptyState description="Нет активности. Начните работу." />
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
