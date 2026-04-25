import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { EmptyState, FinanceOverview } from "@shared/brand/components";
import { getPlanByCode, getPlansByAudience } from "@shared/subscriptions/catalog";
import { resolveClientKind, resolveClientSubscriptionTier } from "../access/clientWorkspace";
import { fetchGamificationSummary, fetchMySubscription, fetchSubscriptionBenefits } from "../api/subscriptions";
import { useAuth } from "../auth/AuthContext";
import { useClient } from "../auth/ClientContext";
import { AppErrorState, AppLoadingState } from "../components/states";
import type { ClientSubscription, GamificationSummary, SubscriptionBenefits } from "../types/subscriptions";

const BASE_MODULE_LABELS: Record<string, string> = {
  dashboard: "Дашборд",
  documents: "Документы",
  analytics: "Аналитика",
  marketplace: "Маркетплейс",
  cards: "Карты",
  expenses: "Операции и расходы",
  reports: "Отчёты",
  limits: "Лимиты",
  users: "Команда",
  fleet: "Автопарк",
  logistics: "Логистика",
  stationsMap: "Карта станций",
  support: "Поддержка",
  apiAccess: "API доступ",
  webhooks: "Webhooks",
  whiteLabel: "White-label",
  payouts: "Payouts",
  crmExport: "Экспорт в CRM/ERP",
};

const MODULE_LABELS = Object.entries(BASE_MODULE_LABELS).reduce<Record<string, string>>((lookup, [key, label]) => {
  const snakeUpperKey = key.replace(/([a-z0-9])([A-Z])/g, "$1_$2").toUpperCase();
  lookup[key] = label;
  lookup[key.toLowerCase()] = label;
  lookup[snakeUpperKey] = label;
  lookup[snakeUpperKey.toLowerCase()] = label;
  return lookup;
}, {});

const EMPTY_VALUE = "—";
const STATUS_LABELS: Record<string, string> = {
  ACTIVE: "Активна",
  FREE: "Free / trial",
  PAUSED: "Приостановлена",
  GRACE: "Grace period",
  EXPIRED: "Истекла",
  CANCELLED: "Остановлена",
};

const resolveModuleLabel = (code: string) => MODULE_LABELS[code] ?? MODULE_LABELS[code.toLowerCase()] ?? code;

const formatMoney = (value?: number | null, currency = "RUB") => {
  if (typeof value !== "number") return "По запросу";
  return new Intl.NumberFormat("ru-RU", { style: "currency", currency, maximumFractionDigits: 0 }).format(value);
};

const formatDate = (value?: string | null) => {
  if (!value) return EMPTY_VALUE;
  return new Date(value).toLocaleDateString("ru-RU");
};

const asRecord = (value: unknown): Record<string, unknown> | null => {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
};

const asRecordArray = (value: unknown): Record<string, unknown>[] =>
  Array.isArray(value)
    ? value.filter((item): item is Record<string, unknown> => Boolean(asRecord(item)))
    : [];

const mapCollectionTitles = (items: Record<string, unknown>[], fallback: string) =>
  items.map((item, index) => {
    const title = typeof item.title === "string" ? item.title : typeof item.name === "string" ? item.name : null;
    return title ?? `${fallback} ${index + 1}`;
  });

const resolveCollectionTitles = (primary: unknown, fallback: unknown, label: string) => {
  const primaryItems = asRecordArray(primary);
  if (primaryItems.length) {
    return mapCollectionTitles(primaryItems, label);
  }
  return mapCollectionTitles(asRecordArray(fallback), label);
};

const resolveVisiblePlanModules = (planCode?: string | null) => {
  const catalogPlan = getPlanByCode(planCode);
  if (!catalogPlan) return [];
  return Object.entries(catalogPlan.modules)
    .filter(([, enabled]) => Boolean(enabled))
    .map(([code]) => resolveModuleLabel(code));
};

export function SubscriptionPage() {
  const { user } = useAuth();
  const { client } = useClient();
  const [subscription, setSubscription] = useState<ClientSubscription | null>(null);
  const [benefits, setBenefits] = useState<SubscriptionBenefits | null>(null);
  const [gamification, setGamification] = useState<GamificationSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    Promise.all([fetchMySubscription(user), fetchSubscriptionBenefits(user), fetchGamificationSummary(user)])
      .then(([subscriptionResponse, benefitsResponse, gamificationResponse]) => {
        if (!active) return;
        setSubscription(subscriptionResponse);
        setBenefits(benefitsResponse);
        setGamification(gamificationResponse);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Не удалось загрузить подписку");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [retryKey, user]);

  const clientKind = resolveClientKind({ client });
  const currentPlanCode = subscription?.plan?.code ?? subscription?.plan_id ?? client?.subscription?.plan_code ?? null;
  const subscriptionTier = resolveClientSubscriptionTier(currentPlanCode);
  const availablePlans = useMemo(() => {
    const plans = getPlansByAudience("CLIENT");
    return plans.filter((plan) => {
      if (clientKind === "INDIVIDUAL") {
        return plan.availableCustomerTypes?.includes("INDIVIDUAL") ?? true;
      }
      return (plan.availableCustomerTypes?.some((item) => item !== "INDIVIDUAL") ?? true) || !plan.availableCustomerTypes;
    });
  }, [clientKind]);

  const enabledModules = useMemo(() => {
    if (benefits?.modules?.length) {
      return benefits.modules.map((module) => resolveModuleLabel(module.module_code));
    }
    return resolveVisiblePlanModules(currentPlanCode);
  }, [benefits?.modules, currentPlanCode]);

  const unavailableModules = useMemo(
    () => (benefits?.unavailable_modules ?? []).map((module) => resolveModuleLabel(module.module_code)),
    [benefits?.unavailable_modules],
  );

  const preview = useMemo(() => asRecord(gamification?.preview), [gamification]);
  const previewAvailable = useMemo(() => asRecord(preview?.["available"]), [preview]);
  const previewPlanTitle = typeof preview?.["plan_title"] === "string" ? preview["plan_title"] : null;
  const previewModules = useMemo(
    () =>
      asRecordArray(preview?.["modules"])
        .map((item) => (typeof item.module_code === "string" ? resolveModuleLabel(item.module_code) : null))
        .filter((item): item is string => Boolean(item)),
    [preview],
  );

  if (loading) {
    return <AppLoadingState label="Загружаем подписку..." />;
  }

  if (error) {
    return <AppErrorState message={error} onRetry={() => setRetryKey((current) => current + 1)} />;
  }

  if (!subscription) {
    return (
      <div className="stack subscription-page">
        <div className="page-header">
          <div>
            <h1>Подписка и тариф</h1>
            <p className="muted">Коммерческий контур, доступные возможности и следующий шаг без скрытой магии.</p>
          </div>
        </div>
        <EmptyState
          title="Подписка пока не назначена"
          description="Сначала завершите онбординг, чтобы портал назначил базовый тариф и открыл доступные модули."
          primaryAction={{ label: "Перейти к онбордингу", to: "/onboarding" }}
          secondaryAction={{ label: "Написать в поддержку", to: "/client/support/new?topic=subscription_change" }}
        />
      </div>
    );
  }

  const achievementTitles = resolveCollectionTitles(gamification?.achievements, previewAvailable?.["achievements"], "Механика");
  const bonusTitles = resolveCollectionTitles(gamification?.bonuses, previewAvailable?.["bonuses"], "Бонус");
  const streakTitles = resolveCollectionTitles(gamification?.streaks, previewAvailable?.["streaks"], "Серия");
  const subscriptionStatus = STATUS_LABELS[subscription.status] ?? subscription.status;
  const supportPlan = client?.subscription?.support_plan?.toUpperCase() ?? EMPTY_VALUE;
  const programTitle = preview ? "Что откроется после апгрейда" : "Программа активности";
  const programDescription = preview
    ? `Страница честно показывает, какие бонусы и механики откроет ${previewPlanTitle ?? "расширенный тариф"}, без декоративных достижений и пустых обещаний.`
    : "Портал показывает, какие бонусы и механики поддерживает ваш тариф. Реальный прогресс появляется по мере использования сервисов.";

  return (
    <div className="stack subscription-page">
      <div className="page-header">
        <div>
          <h1>Подписка и тариф</h1>
          <p className="muted">Коммерческий контур, доступные возможности и следующий шаг без скрытой магии.</p>
        </div>
      </div>

      <div className="surface-toolbar subscription-page__toolbar">
        <div className="stack subscription-page__toolbar-copy">
          <strong>Коммерческий workflow</strong>
          <span className="muted small">
            Портал показывает текущий договор и entitlements. Смена тарифа и модулей идёт через действующий support/commercial contour.
          </span>
        </div>
        <div className="toolbar-actions">
          <Link className="primary" to="/client/support/new?topic=subscription_change">
            Запросить изменение тарифа
          </Link>
          <Link className="ghost" to="/legal">
            Юридические условия
          </Link>
        </div>
      </div>

      <FinanceOverview
        items={[
          {
            id: "client-kind",
            label: "Тип клиента",
            value: clientKind === "BUSINESS" ? "BUSINESS" : "INDIVIDUAL",
            meta: clientKind === "BUSINESS" ? "Коммерческий кабинет" : "Личный контур клиента",
            tone: "info",
          },
          {
            id: "plan",
            label: "Текущий тариф",
            value: subscription.plan?.title ?? currentPlanCode ?? EMPTY_VALUE,
            meta: currentPlanCode ?? EMPTY_VALUE,
            tone: "premium",
          },
          {
            id: "tier",
            label: "Tier",
            value: subscriptionTier,
          },
          {
            id: "status",
            label: "Статус",
            value: subscriptionStatus,
            tone: subscription.status === "ACTIVE" ? "success" : "warning",
          },
          {
            id: "period",
            label: "Период",
            value: `${formatDate(subscription.start_at)} → ${formatDate(subscription.end_at)}`,
          },
          {
            id: "support",
            label: "Support plan",
            value: supportPlan,
          },
        ]}
      />

      <section className="card">
        <div className="card__header">
          <div>
            <h3>Доступные планы</h3>
            <p className="muted">Портал показывает только планы, поддержанные текущим client kind.</p>
          </div>
        </div>
        <div className="subscription-page__plans">
          {availablePlans.map((plan) => {
            const isCurrent = plan.code === currentPlanCode;
            const moduleList = Object.entries(plan.modules)
              .filter(([, enabled]) => Boolean(enabled))
              .map(([code]) => resolveModuleLabel(code));

            return (
              <article key={plan.code} className={`card subscription-page__plan${isCurrent ? " is-current" : ""}`}>
                <div className="subscription-page__plan-header">
                  <div>
                    <h4>{plan.title}</h4>
                    <div className="muted small">{plan.code}</div>
                  </div>
                  {isCurrent ? <span className="badge success">Текущий</span> : null}
                </div>
                <p className="muted">{plan.description}</p>
                <div className="subscription-page__price">
                  <strong>{formatMoney(plan.monthlyPrice ?? null)}</strong>
                  <div className="muted small">
                    {plan.yearlyPrice ? `или ${formatMoney(plan.yearlyPrice)} / год` : "Годовая цена по договору"}
                  </div>
                </div>
                <ul className="subscription-page__list">
                  {plan.bullets.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
                <div className="muted small">Модули: {moduleList.join(", ") || EMPTY_VALUE}</div>
              </article>
            );
          })}
        </div>
      </section>

      <section className="card">
        <div className="card__header">
          <div>
            <h3>Активные возможности</h3>
            <p className="muted">Только реальные entitlements: что уже доступно и что требует смены тарифа.</p>
          </div>
        </div>
        <div className="subscription-page__program-grid">
          <div className="subscription-page__program-card">
            <div className="muted small">Включено сейчас</div>
            {enabledModules.length ? (
              <ul className="subscription-page__list">
                {enabledModules.map((module) => (
                  <li key={module}>{module}</li>
                ))}
              </ul>
            ) : (
              <p className="muted">Активные модули пока не назначены.</p>
            )}
          </div>
          <div className="subscription-page__program-card">
            <div className="muted small">Требует апгрейда</div>
            {unavailableModules.length ? (
              <ul className="subscription-page__list">
                {unavailableModules.map((module) => (
                  <li key={module}>{module}</li>
                ))}
              </ul>
            ) : (
              <p className="muted">Все доступные модули уже включены.</p>
            )}
          </div>
        </div>
      </section>

      <section className="card">
        <div className="card__header">
          <div>
            <h3>{programTitle}</h3>
            <p className="muted">{programDescription}</p>
          </div>
        </div>
        <div className="subscription-page__program-grid">
          <div className="subscription-page__program-card">
            <div className="muted small">Достижения</div>
            {achievementTitles.length ? (
              <ul className="subscription-page__list">
                {achievementTitles.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="muted">Для этого тарифа дополнительные механики пока не настроены.</p>
            )}
          </div>
          <div className="subscription-page__program-card">
            <div className="muted small">Бонусы и скидки</div>
            {bonusTitles.length ? (
              <ul className="subscription-page__list">
                {bonusTitles.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="muted">Бонусные механики появятся после активации подходящего тарифа.</p>
            )}
          </div>
          <div className="subscription-page__program-card">
            <div className="muted small">Серии активности</div>
            {streakTitles.length ? (
              <ul className="subscription-page__list">
                {streakTitles.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="muted">Серии появятся после первых регулярных действий в продукте.</p>
            )}
          </div>
        </div>
        {previewPlanTitle || previewModules.length ? (
          <div className="subscription-page__preview">
            <strong>Preview апгрейда</strong>
            <div className="muted small">
              {previewPlanTitle
                ? `Что будет доступно в плане ${previewPlanTitle}.`
                : "Расширенный тариф откроет дополнительные модули и сценарии."}
            </div>
            {previewModules.length ? <div className="muted">Модули: {previewModules.join(", ")}</div> : null}
          </div>
        ) : null}
      </section>

      <section className="card">
        <div className="card__header">
          <div>
            <h3>Следующий шаг</h3>
            <p className="muted">
              Страница не обещает self-service billing change там, где owner находится в коммерческом процессе.
            </p>
          </div>
        </div>
        <div className="subscription-page__workflow">
          <div className="subscription-page__workflow-step">
            <strong>1. Опишите сценарий</strong>
            <span className="muted small">Какие модули, команда или объём документов вам нужны.</span>
          </div>
          <div className="subscription-page__workflow-step">
            <strong>2. Подтвердите условия</strong>
            <span className="muted small">
              Менеджер сверит тариф, поддержку и ограничения без скрытых изменений billing semantics.
            </span>
          </div>
          <div className="subscription-page__workflow-step">
            <strong>3. Получите обновлённые права</strong>
            <span className="muted small">После подтверждения портал покажет новые entitlements и модули.</span>
          </div>
        </div>
      </section>
    </div>
  );
}

export default SubscriptionPage;
