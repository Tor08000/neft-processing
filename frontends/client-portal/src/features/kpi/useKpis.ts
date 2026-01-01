import { useCallback, useEffect, useMemo, useState } from "react";
import type { OperationSummary } from "../../types/operations";
import type { SpendDashboardSummary } from "../../types/spend";
import { useAuth } from "../../auth/AuthContext";
import { fetchKpiSummary } from "./api";
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
  error: string | null;
  isLoading: boolean;
  isMock: boolean;
  reload: () => void;
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
  const { user } = useAuth();
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
      error: null,
      isLoading: false,
      isMock: true,
      reload: () => undefined,
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
  const [reloadKey, setReloadKey] = useState(0);
  const reload = useCallback(() => setReloadKey((prev) => prev + 1), []);

  const toastOnce = useCallback(
    (key: string, text: string) => {
      if (!showToast || typeof window === "undefined") return;
      try {
        const storageKey = `mock-toast-${key}`;
        if (sessionStorage.getItem(storageKey)) {
          return;
        }
        sessionStorage.setItem(storageKey, "1");
      } catch {
        return;
      }
      showToast("info", text);
    },
    [showToast],
  );

  useEffect(() => {
    let active = true;
    const token = user?.token;
    if (!token) {
      setApiData({ kpis: [], hints: [], error: "Требуется авторизация", isLoading: false, isMock: false, reload });
      return;
    }
    setApiData((prev) =>
      prev
        ? { ...prev, isLoading: true, error: null }
        : { kpis: [], hints: [], error: null, isLoading: true, isMock: false, reload },
    );
    fetchKpiSummary(token)
      .then((data) => {
        if (!active) return;
        const kpis = data.kpis.map((item) => {
          const delta = item.delta ?? undefined;
          const trend = delta === undefined ? undefined : delta > 0 ? "up" : delta < 0 ? "down" : "flat";
          return {
            id: item.key,
            title: item.title,
            value:
              item.unit === "money"
                ? formatMoney(item.value)
                : item.unit === "percent"
                  ? formatPercent(item.value, 1)
                  : formatCount(item.value),
            current: item.value,
            subvalue: `за ${data.window_days} дней`,
            delta: delta === undefined ? undefined : formatDeltaPercent(delta),
            trend,
            goodWhen: item.good_when,
            unit: item.unit,
            target: item.target ?? undefined,
            progress: item.progress ?? undefined,
          };
        });
        setApiData({ kpis, hints: [], error: null, isLoading: false, isMock: false, reload });
      })
      .catch((err) => {
        if (!active) return;
        if (isDev) {
          toastOnce("client-kpi", "Mock mode: KPI");
          setApiData({ ...mockData, reload });
          return;
        }
        const message = err instanceof Error ? err.message : "Не удалось загрузить KPI";
        setApiData({ kpis: [], hints: [], error: message, isLoading: false, isMock: false, reload });
      });
    return () => {
      active = false;
    };
  }, [isDev, mockData, reload, reloadKey, toastOnce, user?.token]);

  return apiData ?? mockData;
};
