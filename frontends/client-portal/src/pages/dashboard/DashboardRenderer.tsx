import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import type { ClientDashboardResponse, ClientDashboardWidget } from "../../types/portal";
import { formatDate, formatDateTime, formatMoney } from "../../utils/format";
import { EmptyState } from "@shared/brand/components";

const EMPTY_LABEL = "Нет данных";

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

// Generic documents discovery from dashboard widgets must stay on the canonical /client/documents*
// contour. Do not point new dashboard links at the legacy /documents* compatibility surface.
const widgetLinks: Record<string, string> = {
  total_spend_30d: "/client/analytics",
  transactions_30d: "/client/analytics",
  spend_timeseries_30d: "/client/analytics",
  top_cards: "/cards",
  top_drivers_cards: "/client/analytics",
  support_overview: "/client/support",
  health_exports_email: "/client/exports",
  slo_health: "/client/slo",
  invoices_count_30d: "/billing",
  recent_documents: "/client/documents",
  exports_recent: "/client/exports",
  active_cards: "/cards",
  blocked_cards: "/cards",
  alerts: "/limits/templates",
  my_cards_count: "/cards",
  recent_transactions: "/operations",
  card_limits: "/cards",
};

const widgetTitles: Record<string, { title: string; subtitle?: string }> = {
  total_spend_30d: { title: "Общие расходы", subtitle: "За последние 30 дней" },
  transactions_30d: { title: "Транзакции", subtitle: "За последние 30 дней" },
  spend_timeseries_30d: { title: "Расходы по дням", subtitle: "30 дней" },
  top_cards: { title: "Топ карт", subtitle: "5 карт с максимальным расходом" },
  top_drivers_cards: { title: "Топ водителей и карт", subtitle: "Лидеры по расходам" },
  support_overview: { title: "Поддержка", subtitle: "Статусы за 30 дней" },
  health_exports_email: { title: "Системное здоровье", subtitle: "Экспорты и почта" },
  slo_health: { title: "SLO Health", subtitle: "Окна 7d / 30d" },
  invoices_count_30d: { title: "Счета и акты", subtitle: "За последние 30 дней" },
  recent_documents: { title: "Недавние документы", subtitle: "Последние 5" },
  exports_recent: { title: "Экспорты", subtitle: "Последние задачи" },
  active_cards: { title: "Активные карты" },
  blocked_cards: { title: "Заблокированные карты" },
  alerts: { title: "Предупреждения", subtitle: "Лимиты и аномалии" },
  my_cards_count: { title: "Мои карты" },
  recent_transactions: { title: "Мои операции" },
  card_limits: { title: "Лимиты карт" },
};

// Generic CTA entry points follow the same rule: use /client/documents for general discovery.
const ctaActions: Record<string, Array<{ label: string; to: string; variant?: "primary" | "secondary" }>> = {
  owner_actions: [
    { label: "Создать отчёт", to: "/client/exports", variant: "primary" },
    { label: "Перейти в аналитику", to: "/client/analytics" },
  ],
  accountant_actions: [
    { label: "Экспорт транзакций", to: "/client/exports", variant: "primary" },
    { label: "Документы", to: "/client/documents" },
  ],
  fleet_actions: [
    { label: "Карты", to: "/cards", variant: "primary" },
    { label: "Лимиты", to: "/limits/templates" },
  ],
  driver_actions: [{ label: "Мои карты", to: "/cards", variant: "primary" }],
};

const ctaMeta: Record<string, { title: string; subtitle: string }> = {
  owner_actions: {
    title: "Следующие шаги владельца",
    subtitle: "Быстрые переходы в контуры, которые закрывают контроль расходов и отчётности.",
  },
  accountant_actions: {
    title: "Следующие шаги бухгалтерии",
    subtitle: "Документы, выгрузки и проверка периода без лишних кликов по меню.",
  },
  fleet_actions: {
    title: "Следующие шаги fleet-контура",
    subtitle: "Карты, лимиты и предупреждения, которые помогают удерживать парк в рабочем коридоре.",
  },
  driver_actions: {
    title: "Следующие шаги по смене",
    subtitle: "Самые частые действия для водителя вынесены в один понятный блок.",
  },
};

const dashboardSpotlight: Record<
  string,
  {
    title: string;
    description: string;
    hint: string;
    primaryAction: { label: string; to: string };
    secondaryAction: { label: string; to: string };
  }
> = {
  OWNER: {
    title: "Держите под контролем расходы и service health",
    description: "Панель собрана вокруг owner-сценария: аналитика, поддержка и системные сигналы уже сведены в один рабочий обзор.",
    hint: "Начните с аналитики, если нужно быстро проверить расход за период, затем спускайтесь к support и SLO.",
    primaryAction: { label: "Открыть аналитику", to: "/client/analytics" },
    secondaryAction: { label: "Перейти в поддержку", to: "/client/support" },
  },
  ACCOUNTANT: {
    title: "Закройте документы и выгрузки за период",
    description: "Для бухгалтерии мы держим рядом документы, экспортные задачи и сигналы по выставленным счетам без декоративных блоков.",
    hint: "Если период ещё не закрыт, сначала проверьте документы, затем экспорт и billing-контур.",
    primaryAction: { label: "Открыть документы", to: "/client/documents" },
    secondaryAction: { label: "Открыть экспорты", to: "/client/exports" },
  },
  FLEET_MANAGER: {
    title: "Проверьте парк и ограничения до того, как появятся инциденты",
    description: "Главные сигналы fleet-контура собраны по картам, лимитам и предупреждениям, чтобы следующий шаг был виден сразу.",
    hint: "Если предупреждений пока нет, используйте блок как быстрый вход в лимиты и уведомления.",
    primaryAction: { label: "Открыть карты", to: "/cards" },
    secondaryAction: { label: "Открыть лимиты", to: "/limits/templates" },
  },
  DRIVER: {
    title: "Проверьте карту и последние операции перед поездкой",
    description: "Для водителя остаются только рабочие сигналы: доступные карты, последние списания и текущие лимиты.",
    hint: "Если лимиты не заполнены, откройте карту и уточните ограничения перед следующей операцией.",
    primaryAction: { label: "Открыть карты", to: "/cards" },
    secondaryAction: { label: "Открыть операции", to: "/operations" },
  },
};

type DashboardRendererProps = {
  dashboard: ClientDashboardResponse;
};

type ChartPoint = { date: string; value: number };

type TopItem = { id: string; label: string; spend: number; count: number };

type DriverTopItem = { id: string; label: string; spend: number; count: number };

type SupportData = {
  open_tickets: number;
  sla_breaches_first: number;
  sla_breaches_resolution: number;
};

type HealthData = {
  exports_running: number;
  exports_failed: number;
  email_failures_24h: number;
};

type SloHealthData = {
  status: "green" | "yellow" | "red";
  breaches_7d: number;
  breaches_30d: number;
};

type RecentDocument = { id: string; type: string; status: string; date: string };

type ExportItem = { id: string; report_type: string; status: string; created_at: string; eta_at?: string | null };

type RecentTransaction = {
  id: string;
  occurred_at: string;
  amount: number;
  currency: string;
  card_label: string;
};

type CardLimit = { type: string; amount: number; currency: string };

type CardLimitsItem = { card_id: string; label: string; limits: CardLimit[] };

type TopDriversCardsData = { drivers: DriverTopItem[]; cards: TopItem[] };

const formatKpiValue = (value: number, currency?: string) => {
  if (currency) {
    return formatMoney(value, currency);
  }
  return new Intl.NumberFormat("ru-RU").format(value);
};

function WidgetCard({
  title,
  subtitle,
  link,
  children,
}: {
  title: string;
  subtitle?: string;
  link?: string;
  children: ReactNode;
}) {
  return (
    <section className="card dashboard-widget">
      <div className="card__header">
        <div>
          <h2>{title}</h2>
          {subtitle ? <p className="muted">{subtitle}</p> : null}
        </div>
        {link ? (
          <Link className="ghost" to={link}>
            Перейти
          </Link>
        ) : null}
      </div>
      {children}
    </section>
  );
}

function RoleSpotlight({ role }: { role: string }) {
  const spotlight = dashboardSpotlight[role];
  if (!spotlight) {
    return null;
  }

  return (
    <section className="card dashboard-widget">
      <div className="card__header">
        <div>
          <h2>{spotlight.title}</h2>
          <p className="muted">{spotlight.description}</p>
        </div>
        <span className="neft-chip neft-chip-info">{role}</span>
      </div>
      <div className="dashboard-actions">
        <Link className="neft-button neft-btn-primary" to={spotlight.primaryAction.to}>
          {spotlight.primaryAction.label}
        </Link>
        <Link className="ghost" to={spotlight.secondaryAction.to}>
          {spotlight.secondaryAction.label}
        </Link>
      </div>
      <div className="muted small">{spotlight.hint}</div>
    </section>
  );
}

function renderListEmptyState(key: string) {
  if (key === "recent_documents") {
    return (
      <EmptyState
        title="Документы появятся после закрытия периода"
        description="Пока здесь пусто, вы можете открыть общий журнал документов и проверить, не ждут ли вас счета или акты."
        primaryAction={{ label: "Открыть документы", to: "/client/documents" }}
      />
    );
  }

  if (key === "exports_recent") {
    return (
      <EmptyState
        title="Экспорты ещё не запускались"
        description="Когда появятся выгрузки, они будут видны здесь вместе со статусом и ETA."
        primaryAction={{ label: "Создать экспорт", to: "/client/exports" }}
      />
    );
  }

  if (key === "recent_transactions") {
    return (
      <EmptyState
        title="Операций пока нет"
        description="После первых транзакций карточка покажет недавние списания и время операции."
        primaryAction={{ label: "Открыть операции", to: "/operations" }}
      />
    );
  }

  if (key === "card_limits") {
    return (
      <EmptyState
        title="Лимиты карт не настроены"
        description="Настройте ограничения, чтобы следующий расход не уходил в ручной разбор."
        primaryAction={{ label: "Открыть лимиты", to: "/limits/templates" }}
      />
    );
  }

  if (key === "alerts") {
    return (
      <EmptyState
        title="Активных предупреждений нет"
        description="Когда лимиты, аномалии или уведомления потребуют внимания, эта карточка станет рабочим inbox, а не пустой заглушкой."
        primaryAction={{ label: "Открыть уведомления", to: "/fleet/notifications" }}
        secondaryAction={{ label: "Проверить лимиты", to: "/limits/templates" }}
      />
    );
  }

  if (key === "top_cards") {
    return (
      <EmptyState
        title="Пока нет лидеров по расходам"
        description="Карточка наполнится, когда появится достаточно операций для ранжирования карт."
        primaryAction={{ label: "Открыть аналитику", to: "/client/analytics" }}
      />
    );
  }

  return <EmptyState title="Пока нет данных" description="Карточка наполнится, когда owner начнёт возвращать реальные данные для этого контура." />;
}

function renderUnavailableWidgetState(key: string) {
  const link = widgetLinks[key];
  return (
    <EmptyState
      title="Данные временно недоступны"
      description="Карточка появится, когда связанные операции будут доступны для расчёта."
      primaryAction={link ? { label: "Открыть раздел", to: link } : undefined}
    />
  );
}

function Sparkline({ points }: { points: ChartPoint[] }) {
  if (!points.length) {
    return <div className="muted small">{EMPTY_LABEL}</div>;
  }
  const values = points.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const width = 220;
  const height = 60;
  const padding = 6;
  const step = points.length > 1 ? (width - padding * 2) / (points.length - 1) : 0;
  const coords = points.map((point, index) => {
    const x = padding + index * step;
    const y = height - padding - ((point.value - min) / range) * (height - padding * 2);
    return `${x},${y}`;
  });
  const lastCoord = coords[coords.length - 1];
  const lastY = lastCoord ? Number(lastCoord.split(",")[1]) : 0;
  return (
    <svg className="dashboard-sparkline" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="chart">
      <polyline
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
        strokeLinecap="round"
        points={coords.join(" ")}
      />
      <circle cx={width - padding} cy={lastY} r="3" fill="currentColor" />
    </svg>
  );
}

function renderListItems(data: unknown, timezone: string, key: string) {
  if (!Array.isArray(data) || data.length === 0) {
    return renderListEmptyState(key);
  }

  if (key === "top_cards") {
    return (
      <ul className="dashboard-list">
        {(data as TopItem[]).map((item) => (
          <li key={item.id} className="dashboard-list__item">
            <div>
              <div className="dashboard-list__title">{item.label}</div>
              <div className="muted small">{item.count} транзакций</div>
            </div>
            <div className="dashboard-list__value">{formatMoney(item.spend, "RUB")}</div>
          </li>
        ))}
      </ul>
    );
  }

  if (key === "recent_documents") {
    return (
      <ul className="dashboard-list">
        {(data as RecentDocument[]).map((item) => (
          <li key={item.id} className="dashboard-list__item">
            <div>
              <div className="dashboard-list__title">{item.type}</div>
              <div className="muted small">{formatDate(item.date, timezone)}</div>
            </div>
            <div className="dashboard-list__value">{item.status}</div>
          </li>
        ))}
      </ul>
    );
  }

  if (key === "exports_recent") {
    return (
      <ul className="dashboard-list">
        {(data as ExportItem[]).map((item) => (
          <li key={item.id} className="dashboard-list__item">
            <div>
              <div className="dashboard-list__title">{item.report_type}</div>
              <div className="muted small">{formatDateTime(item.created_at, timezone)}</div>
              {item.eta_at ? <div className="muted small">ETA {formatDateTime(item.eta_at, timezone)}</div> : null}
            </div>
            <div className="dashboard-list__value">{item.status}</div>
          </li>
        ))}
      </ul>
    );
  }

  if (key === "recent_transactions") {
    return (
      <ul className="dashboard-list">
        {(data as RecentTransaction[]).map((item) => (
          <li key={item.id} className="dashboard-list__item">
            <div>
              <div className="dashboard-list__title">{item.card_label}</div>
              <div className="muted small">{formatDateTime(item.occurred_at, timezone)}</div>
            </div>
            <div className="dashboard-list__value">{formatMoney(item.amount, item.currency)}</div>
          </li>
        ))}
      </ul>
    );
  }

  if (key === "card_limits") {
    return (
      <div className="dashboard-limits">
        {(data as CardLimitsItem[]).map((item) => (
          <div key={item.card_id} className="dashboard-limits__card">
            <div className="dashboard-list__title">{item.label}</div>
            {item.limits.length ? (
              <ul className="dashboard-limits__list">
                {item.limits.map((limit, index) => (
                  <li key={`${item.card_id}-${limit.type}-${index}`}>
                    {limit.type}: {formatMoney(limit.amount, limit.currency)}
                  </li>
                ))}
              </ul>
            ) : (
              <div className="muted small">{EMPTY_LABEL}</div>
            )}
          </div>
        ))}
      </div>
    );
  }

  if (key === "alerts") {
    return (
      <ul className="dashboard-list">
        {(data as Array<Record<string, unknown>>).map((item, index) => (
          <li key={String(item.id ?? index)} className="dashboard-list__item">
            <div>
              <div className="dashboard-list__title">{String(item.title ?? item.message ?? "Предупреждение")}</div>
              <div className="muted small">
                {item.occurred_at ? formatDateTime(String(item.occurred_at), timezone) : "Требует внимания"}
              </div>
            </div>
            <div className="dashboard-list__value">{String(item.severity ?? item.status ?? "OPEN")}</div>
          </li>
        ))}
      </ul>
    );
  }

  return renderListEmptyState(key);
}

function TopDriversCards({ data }: { data: TopDriversCardsData }) {
  const drivers = data.drivers ?? [];
  const cards = data.cards ?? [];
  return (
    <div className="dashboard-grid">
      <div className="dashboard-sublist">
        <div className="dashboard-sublist__title">Водители</div>
        {drivers.length ? (
          <ul className="dashboard-list">
            {drivers.map((item) => (
              <li key={item.id} className="dashboard-list__item">
                <div>
                  <div className="dashboard-list__title">{item.label}</div>
                  <div className="muted small">{item.count} транзакций</div>
                </div>
                <div className="dashboard-list__value">{formatMoney(item.spend, "RUB")}</div>
              </li>
            ))}
          </ul>
        ) : (
          <div className="muted small">{EMPTY_LABEL}</div>
        )}
      </div>
      <div className="dashboard-sublist">
        <div className="dashboard-sublist__title">Карты</div>
        {cards.length ? (
          <ul className="dashboard-list">
            {cards.map((item) => (
              <li key={item.id} className="dashboard-list__item">
                <div>
                  <div className="dashboard-list__title">{item.label}</div>
                  <div className="muted small">{item.count} транзакций</div>
                </div>
                <div className="dashboard-list__value">{formatMoney(item.spend, "RUB")}</div>
              </li>
            ))}
          </ul>
        ) : (
          <div className="muted small">{EMPTY_LABEL}</div>
        )}
      </div>
    </div>
  );
}

function SupportHealth({ data }: { data: SupportData }) {
  const breaches = (data?.sla_breaches_first ?? 0) + (data?.sla_breaches_resolution ?? 0);
  return (
    <div className="dashboard-health">
      <div className="dashboard-health__item">
        <div className="dashboard-health__label">Открытые тикеты</div>
        <div className="dashboard-health__value">{data?.open_tickets ?? 0}</div>
      </div>
      <div className="dashboard-health__item">
        <div className="dashboard-health__label">Нарушения SLA</div>
        <div className="dashboard-health__value">{breaches}</div>
      </div>
    </div>
  );
}

function SystemHealth({ data }: { data: HealthData }) {
  return (
    <div className="dashboard-health">
      <div className="dashboard-health__item">
        <div className="dashboard-health__label">Экспорты в работе</div>
        <div className="dashboard-health__value">{data?.exports_running ?? 0}</div>
      </div>
      <div className="dashboard-health__item">
        <div className="dashboard-health__label">Экспорты с ошибкой</div>
        <div className="dashboard-health__value">{data?.exports_failed ?? 0}</div>
      </div>
      <div className="dashboard-health__item">
        <div className="dashboard-health__label">Ошибки email (24ч)</div>
        <div className="dashboard-health__value">{data?.email_failures_24h ?? 0}</div>
      </div>
    </div>
  );
}

function SloHealth({ data }: { data: SloHealthData }) {
  const status = data?.status ?? "green";
  const badgeClass =
    status === "red" ? "pill pill--danger" : status === "yellow" ? "pill pill--warning" : "pill pill--success";
  return (
    <div className="dashboard-health">
      <div className="dashboard-health__item">
        <div className="dashboard-health__label">Status</div>
        <div className="dashboard-health__value">
          <span className={badgeClass}>{status.toUpperCase()}</span>
        </div>
      </div>
      <div className="dashboard-health__item">
        <div className="dashboard-health__label">Breaches 7d</div>
        <div className="dashboard-health__value">{data?.breaches_7d ?? 0}</div>
      </div>
      <div className="dashboard-health__item">
        <div className="dashboard-health__label">Breaches 30d</div>
        <div className="dashboard-health__value">{data?.breaches_30d ?? 0}</div>
      </div>
    </div>
  );
}

function renderWidget(widget: ClientDashboardWidget, timezone: string) {
  const meta = widgetTitles[widget.key] ?? { title: widget.key };
  const link = widgetLinks[widget.key];

  if (widget.type === "kpi") {
    const data = isRecord(widget.data) ? widget.data : null;
    if (typeof data?.value !== "number") {
      return (
        <WidgetCard title={meta.title} subtitle={meta.subtitle} link={link}>
          {renderUnavailableWidgetState(widget.key)}
        </WidgetCard>
      );
    }
    const value = data.value;
    const currency = typeof data.currency === "string" ? data.currency : undefined;
    return (
      <WidgetCard title={meta.title} subtitle={meta.subtitle} link={link}>
        <div className="kpi-card">
          <div className="kpi-card__value">{formatKpiValue(value, currency)}</div>
        </div>
      </WidgetCard>
    );
  }

  if (widget.type === "chart") {
    const points = Array.isArray(widget.data) ? (widget.data as ChartPoint[]) : [];
    return (
      <WidgetCard title={meta.title} subtitle={meta.subtitle} link={link}>
        <Sparkline points={points} />
      </WidgetCard>
    );
  }

  if (widget.type === "list") {
    if (widget.key === "top_drivers_cards") {
      const data = (widget.data as TopDriversCardsData) ?? { drivers: [], cards: [] };
      return (
        <WidgetCard title={meta.title} subtitle={meta.subtitle} link={link}>
          <TopDriversCards data={data} />
        </WidgetCard>
      );
    }
    return (
      <WidgetCard title={meta.title} subtitle={meta.subtitle} link={link}>
        {renderListItems(widget.data, timezone, widget.key)}
      </WidgetCard>
    );
  }

  if (widget.type === "health") {
    if (widget.key === "support_overview") {
      return (
        <WidgetCard title={meta.title} subtitle={meta.subtitle} link={link}>
          <SupportHealth data={widget.data as SupportData} />
        </WidgetCard>
      );
    }
    if (widget.key === "slo_health") {
      return (
        <WidgetCard title={meta.title} subtitle={meta.subtitle} link={link}>
          <SloHealth data={widget.data as SloHealthData} />
        </WidgetCard>
      );
    }
    return (
      <WidgetCard title={meta.title} subtitle={meta.subtitle} link={link}>
        <SystemHealth data={widget.data as HealthData} />
      </WidgetCard>
    );
  }

  if (widget.type === "cta") {
    const actions = ctaActions[widget.key] ?? [];
    const meta = ctaMeta[widget.key] ?? {
      title: "Следующие шаги",
      subtitle: "Откройте нужный раздел без лишней навигации.",
    };
    return (
      <section className="card dashboard-widget">
        <div className="card__header">
          <div>
            <h2>{meta.title}</h2>
            <p className="muted">{meta.subtitle}</p>
          </div>
        </div>
        <div className="dashboard-actions">
          {actions.map((action) => (
            <Link
              key={action.label}
              className={action.variant === "primary" ? "neft-button neft-btn-primary" : "ghost"}
              to={action.to}
            >
              {action.label}
            </Link>
          ))}
        </div>
      </section>
    );
  }

  return null;
}

export function DashboardRenderer({ dashboard }: DashboardRendererProps) {
  return (
    <div className="dashboard-grid" aria-live="polite">
      <RoleSpotlight role={dashboard.role} />
      {dashboard.widgets.map((widget) => (
        <div key={`${widget.type}-${widget.key}`}>{renderWidget(widget, dashboard.timezone)}</div>
      ))}
    </div>
  );
}
