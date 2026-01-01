import { useEffect, useMemo, useState } from "react";
import type { OperationSummary } from "../../types/operations";
import type { SpendDashboardSummary } from "../../types/spend";
import { fetchKpis } from "./api";
import { formatCount, formatDeltaPercent, formatMoney, formatPercent } from "./formatters";
import type { KpiCardData, KpiHint } from "./types";

interface KpiContext {
  summary: SpendDashboardSummary | null;
  operations: OperationSummary[];
  docsAttention: number;
  exportsAttention: number;
  showToast?: (kind: "success" | "error" | "info", text: string) => void;
}

interface KpiResponse {
  kpis: KpiCardData[];
  hints: KpiHint[];
}

const getCompletedCount = (operations: OperationSummary[]) =>
  operations.filter((op) => ["APPROVED", "COMPLETED", "SETTLED"].includes(op.status)).length;

export const useKpis = ({
  summary,
  operations,
  docsAttention,
  exportsAttention,
  showToast,
}: KpiContext): KpiResponse => {
  const isDev = import.meta.env.DEV;
  const totalAmount = summary?.total_amount ?? 0;
  const periodLabel = summary?.period ?? "за период";
  const declinedCount = operations.filter((op) => op.status === "DECLINED").length;
  const completedCount = getCompletedCount(operations);
  const invoiceDue = docsAttention;
  const exportsHealth = Math.max(80, 98 - exportsAttention * 2);
  const balanceAmount = 0;

  const totalAmountDelta = summary?.active_limits ?? 0;

  const mockData = useMemo<KpiResponse>(
    () => ({
      kpis: [
        {
          id: "spend-total",
          title: "Spend total",
          value: formatMoney(totalAmount),
          current: totalAmount,
          subvalue: periodLabel,
          delta: summary ? formatDeltaPercent(totalAmountDelta) : undefined,
          trend: totalAmountDelta > 0 ? "up" : totalAmountDelta < 0 ? "down" : "flat",
          goodWhen: "up",
          unit: "money",
          target: 1_200_000,
        },
        {
          id: "declines-total",
          title: "Declines total",
          value: formatCount(declinedCount),
          current: declinedCount,
          subvalue: periodLabel,
          delta: formatDeltaPercent(-3.2),
          trend: "down",
          goodWhen: "down",
          unit: "count",
          target: 2,
        },
        {
          id: "invoices-due",
          title: "Invoices due / overdue",
          value: formatCount(invoiceDue),
          current: invoiceDue,
          subvalue: periodLabel,
          goodWhen: "down",
          unit: "count",
          target: 0,
        },
        {
          id: "orders-completed",
          title: "Orders completed",
          value: formatCount(completedCount),
          current: completedCount,
          subvalue: periodLabel,
          goodWhen: "up",
          unit: "count",
          target: operations.length ? Math.round(operations.length * 0.95) : 95,
        },
        {
          id: "balance",
          title: "Balance",
          value: formatMoney(balanceAmount),
          current: balanceAmount,
          subvalue: "на текущий момент",
          delta: formatDeltaPercent(1.1),
          trend: "up",
          goodWhen: "neutral",
          unit: "money",
        },
      ],
      hints: [
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
      ],
    }),
    [
      balanceAmount,
      completedCount,
      declinedCount,
      exportsHealth,
      invoiceDue,
      operations.length,
      periodLabel,
      summary,
      totalAmount,
      totalAmountDelta,
    ],
  );
  const [apiData, setApiData] = useState<KpiResponse | null>(null);

  useEffect(() => {
    let active = true;
    fetchKpis()
      .then((data) => {
        if (active) {
          setApiData(data);
        }
      })
      .catch(() => {
        if (isDev && showToast) {
          showToast("info", "Mock mode: KPI");
        }
      });
    return () => {
      active = false;
    };
  }, [isDev, showToast]);

  return apiData ?? mockData;
};
