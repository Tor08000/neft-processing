import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { fetchGamificationSummary, fetchMySubscription, fetchSubscriptionBenefits } from "../api/subscriptions";
import type { ClientSubscription, GamificationSummary, SubscriptionBenefits } from "../types/subscriptions";
import { useI18n } from "../i18n";

export function SubscriptionPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [subscription, setSubscription] = useState<ClientSubscription | null>(null);
  const [benefits, setBenefits] = useState<SubscriptionBenefits | null>(null);
  const [gamification, setGamification] = useState<GamificationSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([fetchMySubscription(user), fetchSubscriptionBenefits(user), fetchGamificationSummary(user)])
      .then(([subscriptionResponse, benefitsResponse, gamificationResponse]) => {
        setSubscription(subscriptionResponse);
        setBenefits(benefitsResponse);
        setGamification(gamificationResponse);
      })
      .finally(() => setLoading(false));
  }, [user]);

  const disabledModules = benefits?.unavailable_modules ?? [];
  const enabledModules = benefits?.modules ?? [];
  const getRecordString = (value: unknown, key: string): string | undefined => {
    if (!value || typeof value !== "object") return undefined;
    const record = value as Record<string, unknown>;
    const candidate = record[key];
    return typeof candidate === "string" ? candidate : undefined;
  };
  const previewModules = gamification?.preview?.modules as
    | { module_code: string; enabled: boolean; tier?: string | null }[]
    | undefined;
  const previewAvailable = gamification?.preview?.available as
    | { achievements?: { title: string }[]; streaks?: { title: string }[]; bonuses?: { title: string }[] }
    | undefined;

  const savings = useMemo(() => {
    if (!gamification?.bonuses?.length) return t("subscription.savingsFallback");
    return t("subscription.savingsValue", { value: gamification.bonuses.length });
  }, [gamification, t]);

  const planHeaders = [
    { key: "FREE", label: "FREE / BASIC" },
    { key: "CONTROL", label: "CONTROL" },
    { key: "INTEGRATE", label: "INTEGRATE" },
    { key: "ENTERPRISE", label: "ENTERPRISE" },
  ];
  const tableSections = [
    {
      title: "📊 Таблица: Feature × Plan",
      rows: [
        { key: "feature.portal.core", feature: "Client Portal (основа)", values: ["✅", "✅", "✅", "✅"] },
        {
          key: "feature.portal.entities",
          feature: "Карты / Пользователи / Документы",
          values: ["✅", "✅", "✅", "✅"],
        },
        { key: "feature.export.async_csv", feature: "Асинхронные экспорты (CSV)", values: ["✅", "✅", "✅", "✅"] },
        { key: "feature.notifications.in_app", feature: "Уведомления (in-app)", values: ["✅", "✅", "✅", "✅"] },
        { key: "feature.access.rbac_abac", feature: "Role-based access (RBAC/ABAC)", values: ["✅", "✅", "✅", "✅"] },
        { key: "feature.audit.basic", feature: "Audit (базовый)", values: ["✅", "✅", "✅", "✅"] },
      ],
    },
    {
      title: "📈 Аналитика и отчёты",
      rows: [
        { key: "feature.analytics.summary", feature: "BI Analytics (summary)", values: ["✅", "✅", "✅", "✅"] },
        {
          key: "feature.analytics.drilldown",
          feature: "BI Drill-down (day/card/driver/support)",
          values: ["❌", "✅", "✅", "✅"],
        },
        {
          key: "feature.analytics.advanced",
          feature: "Advanced analytics (trends, comparisons)",
          values: ["❌", "❌", "❌", "✅"],
        },
        { key: "feature.reports.csv", feature: "Scheduled reports (CSV)", values: ["❌", "✅", "✅", "✅"] },
        { key: "feature.reports.xlsx", feature: "Scheduled reports (XLSX)", values: ["❌", "❌", "✅", "✅"] },
        { key: "feature.reports.retention", feature: "Report retention (extended)", values: ["❌", "❌", "✅", "✅"] },
      ],
    },
    {
      title: "⏱ Экспорты и производительность",
      rows: [
        { key: "feature.export.async", feature: "Async exports", values: ["✅", "✅", "✅", "✅"] },
        { key: "feature.export.progress", feature: "Export progress %", values: ["❌", "✅", "✅", "✅"] },
        { key: "feature.export.eta", feature: "Export ETA (predictive)", values: ["❌", "✅", "✅", "✅"] },
        { key: "feature.export.large_100k", feature: "Large exports (100k+)", values: ["❌", "❌", "✅", "✅"] },
        {
          key: "feature.export.streaming_priority",
          feature: "Streaming / priority exports",
          values: ["❌", "❌", "❌", "✅"],
        },
      ],
    },
    {
      title: "🧠 Дашборды и персонализация",
      rows: [
        { key: "feature.dashboards.user", feature: "User dashboards (role-based)", values: ["❌", "✅", "✅", "✅"] },
        { key: "feature.dashboards.health", feature: "Dashboard health widgets", values: ["❌", "❌", "✅", "✅"] },
        { key: "feature.dashboards.custom", feature: "Custom dashboards", values: ["❌", "❌", "❌", "✅"] },
      ],
    },
    {
      title: "🔗 Интеграции (платные add-ons)",
      rows: [
        {
          key: "integration.helpdesk.outbound",
          feature: "Helpdesk outbound (tickets → helpdesk)",
          values: ["❌", "❌", "✅", "✅"],
        },
        {
          key: "integration.helpdesk.inbound",
          feature: "Helpdesk inbound (sync from helpdesk)",
          values: ["❌", "❌", "✅", "✅"],
        },
        {
          key: "integration.erp.accounting",
          feature: "ERP / Accounting integrations",
          values: ["❌", "❌", "❌", "🔧 Add-on"],
        },
        { key: "integration.api.webhooks", feature: "API / Webhooks расширенные", values: ["❌", "❌", "❌", "🔧 Add-on"] },
      ],
    },
    {
      title: "🛡 SLO / SLA и поддержка",
      rows: [
        { key: "support.internal", feature: "Internal support", values: ["✅", "✅", "✅", "✅"] },
        { key: "support.email_notifications", feature: "Email notifications", values: ["LIMITED", "✅", "✅", "✅"] },
        { key: "slo.monitoring.readonly", feature: "SLO monitoring (read-only)", values: ["❌", "❌", "✅", "✅"] },
        { key: "slo.tiers", feature: "SLO tiers (A/B/C)", values: ["❌", "❌", "❌", "✅"] },
        { key: "sla.contractual", feature: "Contractual SLA", values: ["❌", "❌", "❌", "✅"] },
        { key: "support.priority", feature: "Priority support", values: ["❌", "❌", "❌", "✅"] },
        { key: "support.incident_escalation", feature: "Incident management / escalation", values: ["❌", "❌", "❌", "✅"] },
      ],
    },
  ];
  const normalizePlanKey = (value?: string | null) => {
    if (!value) return null;
    const upper = value.toUpperCase();
    if (upper.includes("FREE") || upper.includes("BASIC")) return "FREE";
    if (upper.includes("CONTROL")) return "CONTROL";
    if (upper.includes("INTEGRATE")) return "INTEGRATE";
    if (upper.includes("ENTERPRISE")) return "ENTERPRISE";
    return null;
  };
  const currentPlanLabel = subscription.plan?.title ?? subscription.plan_id;
  const currentPlanKey = normalizePlanKey(subscription.plan?.code ?? subscription.plan_id);
  const highlightStyle = { background: "rgba(58, 130, 255, 0.12)" };

  if (loading) {
    return <div>{t("common.loading")}</div>;
  }

  if (!subscription || !benefits) {
    return <div>{t("subscription.empty")}</div>;
  }

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <section className="card" style={{ padding: 16 }}>
        <h2>Client Portal — Тарифы и возможности (vC)</h2>
        <p className="muted">
          Принцип: мы продаём не функции, а уровень контроля, интеграции, ответственности и SLA. Функции — инструмент
          внутри пакета.
        </p>
        <div style={{ display: "grid", gap: 8 }}>
          <h3>🧩 Линейка тарифов</h3>
          <ul>
            <li>FREE / BASIC — вход и ознакомление</li>
            <li>CONTROL — операционный контроль</li>
            <li>INTEGRATE — интеграция и масштаб</li>
            <li>ENTERPRISE — ответственность и гарантии</li>
          </ul>
          <div className="neft-badge info">Вы сейчас на плане: {currentPlanLabel}</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            <span className="neft-badge success">✅ включено</span>
            <span className="neft-badge neutral">❌ недоступно</span>
            <span className="neft-badge warning">🔧 add-on</span>
            <span className="neft-badge info">LIMITED — только critical events (email)</span>
          </div>
        </div>
      </section>

      {tableSections.map((section) => (
        <section key={section.title} className="card" style={{ padding: 16 }}>
          <h3>{section.title}</h3>
          <div style={{ overflowX: "auto" }}>
            <table className="neft-table">
              <thead>
                <tr>
                  <th>Категория</th>
                  {planHeaders.map((header) => (
                    <th key={header.key} style={currentPlanKey === header.key ? highlightStyle : undefined}>
                      {header.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {section.rows.map((row) => (
                  <tr key={row.key} data-key={row.key}>
                    <td>
                      <div>{row.feature}</div>
                      <div className="muted" style={{ fontSize: 11 }}>
                        {row.key}
                      </div>
                    </td>
                    {row.values.map((value, index) => (
                      <td
                        key={`${row.key}-${index}`}
                        style={currentPlanKey === planHeaders[index]?.key ? highlightStyle : undefined}
                      >
                        {value}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {section.title.includes("add-ons") ? (
            <p className="muted" style={{ marginTop: 12 }}>
              🔧 Add-on — оплачивается отдельно, даже для Enterprise (по договору).
            </p>
          ) : null}
        </section>
      ))}

      <section className="card" style={{ padding: 16 }}>
        <h3>🧾 Пояснения для понимания условий</h3>
        <ul>
          <li>
            <strong>FREE / BASIC</strong> — предоставляется «как есть», без гарантий SLA и интеграций.
          </li>
          <li>
            <strong>CONTROL</strong> — предоставляет инструменты контроля и аналитики, без интеграционных обязательств.
          </li>
          <li>
            <strong>INTEGRATE</strong> — включает интеграционные возможности и мониторинг SLO без контрактных гарантий.
          </li>
          <li>
            <strong>ENTERPRISE</strong> — предоставляется на основании индивидуального договора, включая SLA, SLO tiers,
            поддержку и ответственность.
          </li>
        </ul>
        <p className="muted">Фактические условия определяются договором/счетом/спецификацией.</p>
        <Link className="ghost neft-btn-secondary" to="/legal">
          Юридические условия
        </Link>
      </section>

      <section className="card" style={{ padding: 16 }}>
        <h3>💰 Модель продаж (коротко)</h3>
        <ul>
          <li>FREE / CONTROL — self-serve</li>
          <li>INTEGRATE — self-serve + sales assist</li>
          <li>ENTERPRISE — только через менеджера</li>
        </ul>
        <p className="muted">Интеграции и SLO tiers могут быть включены в пакет или оформлены как отдельные add-ons.</p>
        <Link className="neft-button" to="/client/support/new?topic=sales_enterprise">
          Связаться с менеджером
        </Link>
      </section>

      <section className="card" style={{ padding: 16 }}>
        <h2>{t("subscription.title")}</h2>
        <div style={{ display: "grid", gap: 8 }}>
          <div>
            {t("subscription.currentPlan")}: <strong>{subscription.plan?.title ?? subscription.plan_id}</strong>
          </div>
          <div>
            {t("subscription.status")}: <strong>{subscription.status}</strong>
          </div>
          <div>
            {t("subscription.period")}:
            <strong>
              {subscription.start_at} → {subscription.end_at ?? t("common.notAvailable")}
            </strong>
          </div>
        </div>
      </section>

      <section className="card" style={{ padding: 16 }}>
        <h3>{t("subscription.includes")}</h3>
        <ul>
          {enabledModules.map((module) => (
            <li key={module.module_code}>
              {module.module_code} · {t("subscription.active")}
            </li>
          ))}
        </ul>
      </section>

      <section className="card" style={{ padding: 16 }}>
        <h3>{t("subscription.unavailable")}</h3>
        {disabledModules.length ? (
          <ul>
            {disabledModules.map((module) => (
              <li key={module.module_code} style={{ opacity: 0.6 }}>
                {module.module_code} · {t("subscription.availableInPro")}
              </li>
            ))}
          </ul>
        ) : (
          <div>{t("subscription.allEnabled")}</div>
        )}
      </section>

      <section className="card" style={{ padding: 16 }}>
        <h3>{t("subscription.savingsTitle")}</h3>
        <div>{savings}</div>
      </section>

      <section className="card" style={{ padding: 16 }}>
        <h3>{t("subscription.bonuses")}</h3>
        {gamification?.bonuses?.length ? (
          <ul>
            {gamification.bonuses.map((bonus, index) => {
              const title = getRecordString(bonus, "title");
              return <li key={index}>{title ?? t("subscription.bonusUnlocked")}</li>;
            })}
          </ul>
        ) : (
          <div>{t("subscription.bonusesEmpty")}</div>
        )}
        {gamification?.preview && subscription.status === "FREE" ? (
          <div style={{ marginTop: 12 }}>
            <strong>{t("subscription.previewTitle")}</strong>
            <div>
              {t("subscription.previewSubtitle", {
                plan: getRecordString(gamification.preview, "plan_title") ?? t("common.notAvailable"),
              })}
            </div>
            {previewModules ? (
              <ul>
                {previewModules.map((module, index) => (
                  <li key={`${module.module_code}-${index}`}>{module.module_code}</li>
                ))}
              </ul>
            ) : null}
            {previewAvailable?.bonuses?.length ? (
              <div style={{ marginTop: 8 }}>{t("subscription.availableByPlan")}</div>
            ) : null}
          </div>
        ) : null}
      </section>

      <section className="card" style={{ padding: 16 }}>
        <h3>{t("subscription.streaks")}</h3>
        {gamification?.streaks?.length ? (
          <ul>
            {gamification.streaks.map((streak, index) => {
              const title = getRecordString(streak, "title");
              return <li key={index}>{title ?? t("subscription.streakActive")}</li>;
            })}
          </ul>
        ) : (
          <div>{t("subscription.streaksEmpty")}</div>
        )}
      </section>

      <section className="card" style={{ padding: 16 }}>
        <h3>{t("subscription.achievements")}</h3>
        {gamification?.achievements?.length ? (
          <ul>
            {gamification.achievements.map((achievement, index) => {
              const title = getRecordString(achievement, "title");
              return <li key={index}>{title ?? t("subscription.achievementUnlocked")}</li>;
            })}
          </ul>
        ) : (
          <div>{t("subscription.achievementsEmpty")}</div>
        )}
        {subscription.status === "FREE" && previewAvailable?.achievements?.length ? (
          <div style={{ marginTop: 8 }}>{t("subscription.availableByPlan")}</div>
        ) : null}
      </section>
    </div>
  );
}

export default SubscriptionPage;
