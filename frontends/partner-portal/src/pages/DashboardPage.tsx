import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchPartnerDashboard } from "../api/portal";
import { fetchPartnerBalance, fetchPartnerPayoutPreview, fetchPartnerPayouts } from "../api/partnerFinance";
import { useAuth } from "../auth/AuthContext";
import { usePortal } from "../auth/PortalContext";
import { ErrorState, LoadingState } from "../components/states";
import type { PartnerDashboardSummary } from "../types/portal";
import { formatCurrency } from "../utils/format";
import { canOperatePartnerFinance, resolvePartnerPortalSurface } from "../access/partnerWorkspace";
import { EmptyState, FinanceOverview } from "@shared/brand/components";

type WorkflowCard = {
  title: string;
  description: string;
  to: string;
  actionLabel: string;
};

export function DashboardPage() {
  const { user } = useAuth();
  const { portal } = usePortal();
  const surface = useMemo(() => resolvePartnerPortalSurface(portal), [portal]);
  const canOperateFinance = canOperatePartnerFinance(portal, user?.roles);
  const [summary, setSummary] = useState<PartnerDashboardSummary | null>(null);
  const [balance, setBalance] = useState<{ balance_available?: number; balance_pending?: number; balance_blocked?: number } | null>(null);
  const [blockedCount, setBlockedCount] = useState<number | null>(null);
  const [legalStatus, setLegalStatus] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(surface.workspaceCodes.has("finance"));
  const [error, setError] = useState<string | null>(null);

  const workflowCards = useMemo<WorkflowCard[]>(() => {
    const cards: WorkflowCard[] = [];
    if (surface.workspaceCodes.has("marketplace")) {
      cards.push(
        { title: "Каталог и офферы", description: "Проверьте, что каталог и офферы готовы к новому спросу.", to: "/products", actionLabel: "Открыть каталог" },
        { title: "Заказы", description: "Отслеживайте новые заказы и доводите их до подтверждения без провалов в SLA.", to: "/orders", actionLabel: "Открыть заказы" },
      );
    }
    if (surface.workspaceCodes.has("services")) {
      cards.push(
        { title: "Услуги", description: "Поддерживайте сервисный каталог и статус локаций в рабочем состоянии.", to: "/services", actionLabel: "Открыть услуги" },
        { title: "Заявки услуг", description: "Разберите новые service requests и не дайте очереди зависнуть.", to: "/service-requests", actionLabel: "Открыть заявки" },
      );
    }
    if (surface.workspaceCodes.has("finance")) {
      cards.push(
        { title: "Финансы", description: "Баланс, документы и экспортные операции собраны в одном финансовом контуре.", to: "/finance", actionLabel: "Открыть финансы" },
        { title: "Выплаты", description: "Проверьте статусы payout requests и блокировки до того, как они уйдут в ручной разбор.", to: "/payouts", actionLabel: "Открыть выплаты" },
      );
    }
    cards.push(
      { title: "Обращения", description: "Инциденты, споры и support cases должны быть на виду, а не в боковом хвосте меню.", to: "/support/requests", actionLabel: "Открыть обращения" },
      { title: "Профиль партнёра", description: "Реквизиты, пользователи и legal/profile состояние должны оставаться актуальными.", to: "/partner/profile", actionLabel: "Открыть профиль" },
    );
    return cards;
  }, [surface]);

  const recommendedCard = workflowCards[0] ?? {
    title: "Профиль партнёра",
    description: "Базовые настройки и реквизиты доступны в профиле.",
    to: surface.defaultRoute,
    actionLabel: "Открыть профиль",
  };

  useEffect(() => {
    if (!user || !surface.workspaceCodes.has("finance")) {
      setIsLoading(false);
      setSummary(null);
      setBalance(null);
      setBlockedCount(null);
      setLegalStatus(null);
      return;
    }
    setIsLoading(true);
    setError(null);
    Promise.all([
      fetchPartnerDashboard(user),
      fetchPartnerBalance(user.token),
      fetchPartnerPayoutPreview(user.token),
      fetchPartnerPayouts(user.token),
    ])
      .then(([dashboard, balanceResp, previewResp, payoutsResp]) => {
        setSummary(dashboard);
        setBalance(balanceResp);
        setLegalStatus(previewResp.legal_status ?? portal?.partner?.legal_state?.status ?? null);
        const blocked = (payoutsResp.items ?? []).filter((item) => item.status === "BLOCKED" || item.status === "REJECTED").length;
        setBlockedCount(blocked);
      })
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [portal?.partner?.legal_state?.status, surface, user]);

  if (!user) {
    return null;
  }

  return (
    <div className="stack" aria-live="polite">
      <div className="page-header">
        <div>
          <h1>Кабинет партнёра</h1>
          <p className="muted">Показываем только доступные рабочие разделы для вашего типа партнёра и набора прав.</p>
        </div>
        <Link className="ghost" to={surface.defaultRoute}>
          Открыть основной контур
        </Link>
      </div>

      <section className="card dashboard-widget">
        <div className="card__header">
          <div>
            <h2>Фокус на сейчас</h2>
            <p className="muted">{recommendedCard.description}</p>
          </div>
          <span className="neft-chip neft-chip-info">{surface.kind}</span>
        </div>
        <div className="dashboard-actions">
          <Link className="neft-button neft-btn-primary" to={recommendedCard.to}>
            {recommendedCard.actionLabel}
          </Link>
          <Link className="ghost" to="/support/requests">
            Открыть обращения
          </Link>
        </div>
        <div className="muted small">Разделы подбираются по типу партнёра и правам, поэтому лишние вкладки сюда не подмешиваются.</div>
      </section>

      <section className="card">
        <div className="card__header">
          <div>
            <h2>Операционный обзор</h2>
            <p className="muted">Финансовую сводку показываем только партнёрам с открытым финансовым контуром. Контракты и settlement остаются read-only сигналами внутри финансов, без отдельного workflow.</p>
          </div>
          {surface.workspaceCodes.has("finance") ? (
            <Link className="ghost" to="/finance">
              Открыть финансы
            </Link>
          ) : null}
        </div>
        {!surface.workspaceCodes.has("finance") ? (
          <EmptyState
            title="Финансовый контур скрыт для этого типа партнёра"
            description="Показываем только разделы, которые входят в ваш набор прав. Финансовая сводка не отображается, если партнёр не работает в финансовом контуре."
            primaryAction={{ label: "Открыть профиль", to: "/partner/profile" }}
            secondaryAction={{ label: "Открыть обращения", to: "/support/requests" }}
          />
        ) : isLoading ? (
          <LoadingState />
        ) : error ? (
          <ErrorState description={error} />
        ) : summary ? (
          <>
            <FinanceOverview
              items={[
                {
                  id: "balance",
                  label: "Доступный баланс",
                  value: formatCurrency(balance?.balance_available ?? null),
                  meta: `Ожидает: ${formatCurrency(balance?.balance_pending ?? null)}`,
                  action: <Link to="/finance">Открыть ledger</Link>,
                  tone: "success",
                },
                {
                  id: "blocked",
                  label: "Заблокировано",
                  value: formatCurrency(balance?.balance_blocked ?? null),
                  meta: `Блокированных выплат: ${blockedCount ?? 0}`,
                  action: <Link to="/payouts">Открыть выплаты</Link>,
                  tone: (blockedCount ?? 0) > 0 ? "warning" : "info",
                },
                {
                  id: "legal",
                  label: "Legal статус",
                  value: legalStatus ?? "—",
                  meta: canOperateFinance ? "Выплаты и документы доступны в финансовом контуре." : "Работа с выплатами остаётся в режиме только для чтения.",
                  tone: legalStatus === "VERIFIED" ? "success" : "warning",
                },
                {
                  id: "finance-registers",
                  label: "Contracts and settlements",
                  value: String(summary.active_contracts),
                  meta: summary.current_settlement_period
                    ? `Read-only settlement period: ${summary.current_settlement_period}`
                    : "Read-only owner-backed finance registers are mounted.",
                  action: (
                    <span>
                      <Link to="/contracts">Contracts</Link>
                      <span> / </span>
                      <Link to="/settlements">Settlements</Link>
                    </span>
                  ),
                  tone: "info",
                },
                {
                  id: "payout",
                  label: "Ближайшая выплата",
                  value: summary.upcoming_payout ? formatCurrency(summary.upcoming_payout) : "—",
                  meta: canOperateFinance ? "Можно перейти к payout workflow без дополнительного menu hop." : "Проверьте payout history и блокировки в read-only режиме.",
                  action: <Link to="/payouts">{canOperateFinance ? "Перейти к выплатам" : "Открыть payout history"}</Link>,
                  tone: summary.upcoming_payout ? "premium" : "default",
                },
                {
                  id: "sla",
                  label: "SLA статус",
                  value: summary.sla.status,
                  meta: `Нарушений: ${summary.sla.violations}${summary.sla_score !== null && summary.sla_score !== undefined ? ` · score ${summary.sla_score}` : ""}`,
                  tone: summary.sla.violations > 0 ? "danger" : "success",
                },
              ]}
            />
            <div className="dashboard-actions">
              <Link className="neft-button neft-btn-primary" to="/finance">
                Открыть финансы
              </Link>
              <Link className="ghost" to="/documents">
                Открыть документы
              </Link>
              <Link className="ghost" to="/payouts">
                {canOperateFinance ? "Перейти к выплатам" : "Открыть payout history"}
              </Link>
            </div>
          </>
        ) : (
          <EmptyState
            title="Сводка ещё не готова"
            description="Когда появятся финансовые данные, здесь будут баланс, payout-сигналы и SLA обзор."
            primaryAction={{ label: "Открыть финансы", to: "/finance" }}
          />
        )}
      </section>

      <section className="card">
        <div className="card__header">
          <div>
            <h2>Следующие действия по разделам</h2>
            <p className="muted">Каждый блок ведёт сразу в рабочий раздел, а не в общий кабинет без контекста.</p>
          </div>
        </div>
        <div className="dashboard-grid">
          {workflowCards.map((card) => (
            <section className="card dashboard-widget" key={card.to}>
              <div className="card__header">
                <div>
                  <h3>{card.title}</h3>
                  <p className="muted">{card.description}</p>
                </div>
              </div>
              <div className="dashboard-actions">
                <Link className="neft-button neft-btn-primary" to={card.to}>
                  {card.actionLabel}
                </Link>
              </div>
            </section>
          ))}
        </div>
      </section>
    </div>
  );
}
