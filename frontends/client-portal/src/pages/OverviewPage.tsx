import { useEffect, useMemo, useState } from "react";
import type { ClientMode } from "../layout/ClientLayout";
import { HeroSummaryCard } from "../components/overview/HeroSummaryCard";
import { VehicleCard } from "../components/overview/VehicleCard";
import { OperationRow } from "../components/overview/OperationRow";
import { OverviewEmptyState } from "../components/overview/OverviewEmptyState";
import { useAuth } from "../auth/AuthContext";
import { useClient } from "../auth/ClientContext";
import { isDemoClient } from "@shared/demo/demo";
import { demoOverviewData } from "../demo/demoData";
import "./overview.css";

const MODE_STORAGE_KEY = "neft.client.mode";
const MODE_EVENT = "neftc:client-mode";

const getInitialMode = (): ClientMode => {
  const saved = localStorage.getItem(MODE_STORAGE_KEY);
  if (saved === "fleet" || saved === "personal") {
    return saved;
  }
  return "personal";
};

const formatCurrency = (value: number) =>
  new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB", maximumFractionDigits: 0 }).format(value);
const formatNumber = (value: number) => new Intl.NumberFormat("ru-RU").format(value);

export function OverviewPage() {
  const [mode, setMode] = useState<ClientMode>(getInitialMode());
  const { user } = useAuth();
  const { client } = useClient();
  const isDemoClientAccount = isDemoClient(user?.email ?? client?.user?.email ?? null);
  const isActivated = Boolean(client?.org?.id) && (client?.org?.status ?? client?.org_status) === "ACTIVE";

  useEffect(() => {
    const handleModeChange = (event: Event) => {
      const detail = (event as CustomEvent<ClientMode>).detail;
      if (detail === "fleet" || detail === "personal") {
        setMode(detail);
        return;
      }
      setMode(getInitialMode());
    };

    const handleStorage = (event: StorageEvent) => {
      if (event.key === MODE_STORAGE_KEY) {
        setMode(getInitialMode());
      }
    };

    window.addEventListener(MODE_EVENT, handleModeChange as EventListener);
    window.addEventListener("storage", handleStorage);
    return () => {
      window.removeEventListener(MODE_EVENT, handleModeChange as EventListener);
      window.removeEventListener("storage", handleStorage);
    };
  }, []);

  const data = isDemoClientAccount ? demoOverviewData[mode === "fleet" ? "fleet" : "personal"] : null;
  const vehicles = data?.vehicles ?? [];
  const operations = data?.operations ?? [];
  const hasData = Boolean(data);

  const summaryPrimary = useMemo(
    () => [
      { label: "Баланс", value: formatCurrency(data?.balance ?? 0) },
      { label: "Доступный лимит", value: formatCurrency(data?.limit ?? 0) },
      { label: "Расход (30 дней)", value: `${formatNumber(data?.fuelSpent ?? 0)} л` },
    ],
    [data?.balance, data?.fuelSpent, data?.limit],
  );

  const summarySecondary = useMemo(() => {
    if (!data?.fleetStats) return [];
    return [
      { label: "Автомобилей", value: formatNumber(data.fleetStats.vehicles) },
      { label: "Активных карт", value: formatNumber(data.fleetStats.activeCards) },
      { label: "Лимит топлива", value: formatCurrency(data.fleetStats.fuelLimit) },
      { label: "Ожидают оплаты", value: formatCurrency(data.fleetStats.overdue) },
    ];
  }, [data?.fleetStats]);

  const quickActions = useMemo(() => {
    const base = [
      { label: "Пополнить баланс", variant: "primary" as const },
      { label: "Добавить автомобиль" },
      { label: "Настроить лимиты" },
      { label: "Скачать акт" },
      { label: "Создать отчёт" },
      { label: "Обратиться в поддержку" },
    ];
    if (mode === "personal") {
      return base.slice(0, 4).concat(base[5]);
    }
    return base;
  }, [mode]);

  return (
    <div className="neftc-overview">
      <div className="neftc-overview__header">
        <h1 className="neftc-overview__title">Обзор</h1>
        <p className="neftc-overview__subtitle neftc-text-muted">
          Премиальная сводка по балансу, автопарку и операциям за текущий период.
        </p>
      </div>

      {isActivated ? (
        <div className="neftc-card" style={{ marginBottom: 16, borderColor: "#66bb6a" }}>
          <strong>Аккаунт активирован</strong>
          <div className="neftc-text-muted">Компания подключена. Разделы «Компания», «Пользователи» и «Документы» доступны.</div>
        </div>
      ) : null}

      <section className="neftc-overview__hero-grid">
        {hasData ? (
          <HeroSummaryCard
            primary={summaryPrimary}
            secondary={summarySecondary}
            updatedAt="сегодня, 09:30"
            periodLabel="1–30 сентября"
          />
        ) : (
          <OverviewEmptyState
            title="Нет данных по балансу"
            description="Сводка появится после первой активности."
            actionLabel="Обновить"
            onAction={() => window.location.reload()}
          />
        )}
        <div className="neftc-card neftc-quick-actions">
          <div className="neftc-card__header">
            <h2 className="neftc-card__title">Быстрые действия</h2>
            <span className="neftc-text-muted">Частые сценарии</span>
          </div>
          <div className="neftc-quick-actions__list">
            {quickActions.map((action) => (
              <button
                key={action.label}
                type="button"
                className={action.variant === "primary" ? "neftc-btn-primary" : "neftc-btn-secondary"}
                onClick={() => console.log("action", action.label)}
              >
                {action.label}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="neftc-overview__grid">
        <div className="neftc-card neftc-section">
          <div className="neftc-card__header">
            <div>
              <h2 className="neftc-card__title">Автомобили</h2>
              <p className="neftc-text-muted">Статус и расход топлива</p>
            </div>
            <button type="button" className="neftc-btn-ghost" onClick={() => console.log("open vehicles")}>Посмотреть все</button>
          </div>
          {vehicles.length ? (
            <div className="neftc-vehicles__grid">
              {vehicles.map((vehicle) => (
                <VehicleCard key={vehicle.id} vehicle={vehicle} />
              ))}
            </div>
          ) : (
            <OverviewEmptyState
              title="Автомобили не добавлены"
              description="Добавьте автомобиль, чтобы видеть расходы и аналитику."
              actionLabel="Добавить автомобиль"
              onAction={() => console.log("add vehicle")}
            />
          )}
        </div>

        <div className="neftc-card neftc-section">
          <div className="neftc-card__header">
            <div>
              <h2 className="neftc-card__title">Последние операции</h2>
              <p className="neftc-text-muted">Заправки, платежи и списания</p>
            </div>
            <button type="button" className="neftc-btn-ghost" onClick={() => console.log("open operations")}>Все операции</button>
          </div>
          {operations.length ? (
            <div className="neftc-operations">
              {operations.map((operation) => (
                <OperationRow key={operation.id} operation={operation} />
              ))}
            </div>
          ) : (
            <OverviewEmptyState
              title="Операций пока нет"
              description="Здесь появятся заправки, платежи и списания."
              actionLabel="Обновить"
              onAction={() => console.log("refresh operations")}
            />
          )}
        </div>

        <div className="neftc-card neftc-section neftc-analytics-mini">
          <div className="neftc-card__header">
            <div>
              <h2 className="neftc-card__title">Мини-аналитика</h2>
              <p className="neftc-text-muted">Динамика расходов за 30 дней</p>
            </div>
            <button type="button" className="neftc-btn-ghost" onClick={() => console.log("open analytics")}>Открыть</button>
          </div>
          {hasData ? (
            <div className="neftc-analytics-mini__content">
              <div>
                <div className="neftc-kpi__value">{formatCurrency(mode === "fleet" ? 3560000 : 280000)}</div>
                <div className="neftc-kpi__label">Всего расходов</div>
              </div>
              <div className="neftc-analytics-mini__bars" aria-hidden>
                <span style={{ height: "40%" }} />
                <span style={{ height: "68%" }} />
                <span style={{ height: "52%" }} />
                <span style={{ height: "80%" }} />
                <span style={{ height: "62%" }} />
              </div>
              <div className="neftc-analytics-mini__footer neftc-text-muted">
                Средний чек: {formatCurrency(mode === "fleet" ? 78000 : 9200)} · Топ-станция: Shell
              </div>
            </div>
          ) : (
            <OverviewEmptyState
              title="Нет аналитики"
              description="Данные по расходам появятся после операций."
              actionLabel="Обновить"
              onAction={() => window.location.reload()}
            />
          )}
        </div>
      </section>
    </div>
  );
}
