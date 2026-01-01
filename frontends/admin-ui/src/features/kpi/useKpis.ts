import type { KpiCardData, KpiHint } from "./types";
import { formatCount, formatDeltaPercent, formatPercent } from "./formatters";

interface KpiResponse {
  kpis: KpiCardData[];
  hints: KpiHint[];
}

export const useKpis = (): KpiResponse => {
  // TODO: заменить на реальные метрики с backend (kpi API)
  const kpis: KpiCardData[] = [
    {
      id: "billing-errors",
      title: "Billing errors",
      value: formatCount(0),
      subvalue: "за 7 дней",
      delta: formatDeltaPercent(-12.4),
      trend: "down",
      progress: 1,
      targetLabel: "Цель: 0",
    },
    {
      id: "exports-ontime",
      title: "Exports on-time",
      value: formatPercent(95),
      subvalue: "за 7 дней",
      delta: formatDeltaPercent(1.2),
      trend: "up",
      progress: 0.95,
      targetLabel: "Цель: 98%",
    },
    {
      id: "declines-total",
      title: "Declines total",
      value: formatCount(14),
      subvalue: "за 7 дней",
      delta: formatDeltaPercent(-6.3),
      trend: "down",
      progress: 0.82,
      targetLabel: "Цель: ≤ 10",
    },
    {
      id: "payout-batches",
      title: "Payout batches settled",
      value: formatCount(28),
      subvalue: "за 7 дней",
      delta: formatDeltaPercent(2.1),
      trend: "up",
      progress: 0.7,
      targetLabel: "Цель: 40",
    },
    {
      id: "audit-breaks",
      title: "Audit chain breaks",
      value: formatCount(1),
      subvalue: "за 7 дней",
      delta: formatDeltaPercent(-50),
      trend: "down",
      progress: 0.9,
      targetLabel: "Цель: 0",
    },
  ];

  const hints: KpiHint[] = [
    {
      id: "hint-errors",
      label: "0 ошибок за 7 дней",
      icon: "✓",
      tone: "positive",
    },
    {
      id: "hint-exports",
      label: "Экспорт вовремя: 95%",
      icon: "⏱",
      tone: "neutral",
    },
    {
      id: "hint-sla",
      label: "SLA стабильный: 14 дней без критических сбоев",
      icon: "SLA",
      tone: "neutral",
    },
  ];

  return { kpis, hints };
};
