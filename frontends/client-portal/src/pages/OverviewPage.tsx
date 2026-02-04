import { useEffect, useMemo, useState } from "react";
import type { ClientMode } from "../layout/ClientLayout";
import { HeroSummaryCard } from "../components/overview/HeroSummaryCard";
import { VehicleCard } from "../components/overview/VehicleCard";
import { OperationRow } from "../components/overview/OperationRow";
import { OverviewEmptyState } from "../components/overview/OverviewEmptyState";
import "./overview.css";

const MODE_STORAGE_KEY = "neft.client.mode";
const MODE_EVENT = "neftc:client-mode";

type Vehicle = {
  id: string;
  plate: string;
  model: string;
  status: "active" | "service";
  mileage?: number;
  fuelUsage?: number;
};

type Operation = {
  id: string;
  date: string;
  type: string;
  amount: number;
  status: "paid" | "pending" | "failed";
};

type OverviewData = {
  balance: number;
  limit: number;
  fuelSpent: number;
  fleetStats?: {
    vehicles: number;
    activeCards: number;
    fuelLimit: number;
    overdue: number;
  };
  vehicles: Vehicle[];
  operations: Operation[];
};

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

const mockPersonal: OverviewData = {
  balance: 2450000,
  limit: 3000000,
  fuelSpent: 820,
  vehicles: [
    {
      id: "car-1",
      plate: "А123ВС 77",
      model: "BMW X5 · 2023",
      status: "active",
      mileage: 18450,
      fuelUsage: 8.7,
    },
  ],
  operations: [
    {
      id: "op-1",
      date: "12 сен, 09:10",
      type: "Заправка · Лукойл",
      amount: -4250,
      status: "paid",
    },
    {
      id: "op-2",
      date: "10 сен, 17:40",
      type: "Оплата · Счёт №8421",
      amount: 150000,
      status: "paid",
    },
    {
      id: "op-3",
      date: "07 сен, 12:05",
      type: "Списание · Телематика",
      amount: -8400,
      status: "pending",
    },
  ],
};

const mockFleet: OverviewData = {
  balance: 12450000,
  limit: 18000000,
  fuelSpent: 4120,
  fleetStats: {
    vehicles: 54,
    activeCards: 48,
    fuelLimit: 6200000,
    overdue: 125000,
  },
  vehicles: [
    {
      id: "fleet-1",
      plate: "М245НЕ 199",
      model: "Mercedes Sprinter",
      status: "active",
      mileage: 98200,
      fuelUsage: 12.4,
    },
    {
      id: "fleet-2",
      plate: "С381АК 178",
      model: "Toyota Camry",
      status: "service",
      mileage: 74210,
    },
    {
      id: "fleet-3",
      plate: "Т902ОР 77",
      model: "Volkswagen Crafter",
      status: "active",
      mileage: 65120,
      fuelUsage: 11.8,
    },
  ],
  operations: [
    {
      id: "f-op-1",
      date: "Сегодня, 08:15",
      type: "Заправка · Роснефть",
      amount: -18250,
      status: "paid",
    },
    {
      id: "f-op-2",
      date: "Вчера, 19:30",
      type: "Счёт · Автопарк",
      amount: -56000,
      status: "pending",
    },
    {
      id: "f-op-3",
      date: "08 сен, 11:20",
      type: "Оплата · Счёт №8412",
      amount: 260000,
      status: "paid",
    },
  ],
};

export function OverviewPage() {
  const [mode, setMode] = useState<ClientMode>(getInitialMode());

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

  const data = mode === "fleet" ? mockFleet : mockPersonal;

  const summaryPrimary = useMemo(
    () => [
      { label: "Баланс", value: formatCurrency(data.balance) },
      { label: "Доступный лимит", value: formatCurrency(data.limit) },
      { label: "Расход (30 дней)", value: `${formatNumber(data.fuelSpent)} л` },
    ],
    [data.balance, data.fuelSpent, data.limit],
  );

  const summarySecondary = useMemo(() => {
    if (!data.fleetStats) return [];
    return [
      { label: "Автомобилей", value: formatNumber(data.fleetStats.vehicles) },
      { label: "Активных карт", value: formatNumber(data.fleetStats.activeCards) },
      { label: "Лимит топлива", value: formatCurrency(data.fleetStats.fuelLimit) },
      { label: "Ожидают оплаты", value: formatCurrency(data.fleetStats.overdue) },
    ];
  }, [data.fleetStats]);

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

      <section className="neftc-overview__hero-grid">
        <HeroSummaryCard
          primary={summaryPrimary}
          secondary={summarySecondary}
          updatedAt="сегодня, 09:30"
          periodLabel="1–30 сентября"
        />
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
          {data.vehicles.length ? (
            <div className="neftc-vehicles__grid">
              {data.vehicles.map((vehicle) => (
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
          {data.operations.length ? (
            <div className="neftc-operations">
              {data.operations.map((operation) => (
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
        </div>
      </section>
    </div>
  );
}
