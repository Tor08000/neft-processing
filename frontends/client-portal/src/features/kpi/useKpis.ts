import type { OperationSummary } from "../../types/operations";
import type { SpendDashboardSummary } from "../../types/spend";
import { formatCount, formatDeltaPercent, formatMoney, formatPercent } from "./formatters";
import type { KpiCardData, KpiHint } from "./types";

interface KpiContext {
  summary: SpendDashboardSummary | null;
  operations: OperationSummary[];
  docsAttention: number;
  exportsAttention: number;
}

interface KpiResponse {
  kpis: KpiCardData[];
  hints: KpiHint[];
}

const getCompletedCount = (operations: OperationSummary[]) =>
  operations.filter((op) => ["APPROVED", "COMPLETED", "SETTLED"].includes(op.status)).length;

export const useKpis = ({ summary, operations, docsAttention, exportsAttention }: KpiContext): KpiResponse => {
  // TODO: заменить mock/селекторы на kpi API
  const totalAmount = summary?.total_amount ?? 0;
  const periodLabel = summary?.period ?? "за период";
  const declinedCount = operations.filter((op) => op.status === "DECLINED").length;
  const completedCount = getCompletedCount(operations);
  const invoiceDue = docsAttention;
  const exportsHealth = Math.max(80, 98 - exportsAttention * 2);
  const balanceAmount = 0;

  const totalAmountDelta = summary?.active_limits ?? 0;

  const kpis: KpiCardData[] = [
    {
      id: "spend-total",
      title: "Spend total",
      value: formatMoney(totalAmount),
      subvalue: periodLabel,
      delta: summary ? formatDeltaPercent(totalAmountDelta) : undefined,
      trend: totalAmountDelta > 0 ? "up" : totalAmountDelta < 0 ? "down" : "flat",
      progress: Math.min(totalAmount / 1_200_000, 1),
      targetLabel: `Цель: ${formatMoney(1_200_000)}`,
    },
    {
      id: "declines-total",
      title: "Declines total",
      value: formatCount(declinedCount),
      subvalue: periodLabel,
      delta: formatDeltaPercent(-3.2),
      trend: "down",
      progress: operations.length ? 1 - declinedCount / operations.length : 0.9,
      targetLabel: "Цель: ≤ 2%",
    },
    {
      id: "invoices-due",
      title: "Invoices due / overdue",
      value: formatCount(invoiceDue),
      subvalue: periodLabel,
      progress: invoiceDue === 0 ? 1 : Math.max(0, 1 - invoiceDue / 10),
      targetLabel: "Цель: 0",
    },
    {
      id: "orders-completed",
      title: "Orders completed",
      value: formatCount(completedCount),
      subvalue: periodLabel,
      progress: operations.length ? completedCount / operations.length : 0.75,
      targetLabel: "Цель: 95%",
    },
    {
      id: "balance",
      title: "Balance",
      value: formatMoney(balanceAmount),
      subvalue: "на текущий момент",
      delta: formatDeltaPercent(1.1),
      trend: "up",
      progress: 0.6,
      targetLabel: `Минимум: ${formatMoney(250_000)}`,
    },
  ];

  const hints: KpiHint[] = [
    {
      id: "hint-discipline",
      label: `0 просроченных счетов ${periodLabel}`,
      icon: "✓",
      tone: "positive",
    },
    {
      id: "hint-stability",
      label: "Стабильность: 7 дней без отказов",
      icon: "SLA",
      tone: "neutral",
    },
    {
      id: "hint-exports",
      label: `Экспорт вовремя: ${formatPercent(exportsHealth)}`,
      icon: "⏱",
      tone: "neutral",
    },
  ];

  return { kpis, hints };
};
