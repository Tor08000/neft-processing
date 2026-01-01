import { useCallback, useEffect, useMemo, useState } from "react";
import type { OperationSummary } from "../../types/operations";
import type { SpendDashboardSummary } from "../../types/spend";
import { useAuth } from "../../auth/AuthContext";
import { fetchKpiSummary } from "./api";
import { formatCount, formatDeltaPercent, formatMoney, formatPercent } from "./formatters";
import type { KpiCardData, KpiGoodWhen, KpiHint, KpiStatus, KpiTrend } from "./types";

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

const resolveStatus = (trend?: KpiTrend, goodWhen: KpiGoodWhen = "neutral", deltaValue?: number): KpiStatus => {
  if (!trend || goodWhen === "neutral") {
    if (deltaValue === undefined) return "neutral";
    if (deltaValue > 0) return "good";
    if (deltaValue < 0) return "bad";
    return "neutral";
  }
  if (goodWhen === "up") return trend === "up" ? "good" : trend === "down" ? "bad" : "neutral";
  if (goodWhen === "down") return trend === "down" ? "good" : trend === "up" ? "bad" : "neutral";
  return "neutral";
};

const resolveStatusByTarget = (
  current: number | undefined,
  target: number | null | undefined,
  goodWhen: KpiGoodWhen,
): KpiStatus | null => {
  if (current === undefined || target === null || target === undefined) return null;
  if (goodWhen === "down") return current <= target ? "good" : "bad";
  if (goodWhen === "up") return current >= target ? "good" : "bad";
  return null;
};

const resolveKpiNudges = (key: string) => {
  if (key.includes("decline")) {
    return { actionLabel: "Посмотреть причины отказов", actionTo: "/analytics/declines", praiseLabel: "Отлично, отказов меньше" };
  }
  if (key.includes("export")) {
    return { actionLabel: "Проверить выгрузки", actionTo: "/analytics/exports", praiseLabel: "Отлично, SLA соблюдается" };
  }
  if (key.includes("invoice") || key.includes("document")) {
    return { actionLabel: "Проверить статус документов", actionTo: "/analytics/documents", praiseLabel: "Документы под контролем" };
  }
  if (key.includes("order")) {
    return { actionLabel: "Посмотреть операции", actionTo: "/analytics/marketplace", praiseLabel: "Отлично, заказы идут по плану" };
  }
  if (key.includes("spend") || key.includes("balance")) {
    return { actionLabel: "Проверить лимиты и бюджет", actionTo: "/analytics/spend", praiseLabel: "Бюджет в норме" };
  }
  return { actionLabel: "Проверить показатель", actionTo: "/analytics/spend", praiseLabel: "Отлично, показатель в норме" };
};

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
          deltaValue: summary ? totalAmountDelta : undefined,
          trend: totalAmountDelta > 0 ? "up" : totalAmountDelta < 0 ? "down" : "flat",
          goodWhen: "up",
          status: resolveStatus(totalAmountDelta > 0 ? "up" : totalAmountDelta < 0 ? "down" : "flat", "up", totalAmountDelta),
          ...resolveKpiNudges("spend-total"),
          explainKey: "spend_total",
          explainWindowDays: 7,
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
          deltaValue: -3.2,
          trend: "down",
          goodWhen: "down",
          status: resolveStatus("down", "down", -3.2),
          ...resolveKpiNudges("declines-total"),
          explainKey: "declines_total",
          explainWindowDays: 7,
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
          status: resolveStatusByTarget(invoiceDue, 0, "down") ?? resolveStatus(undefined, "down", undefined),
          ...resolveKpiNudges("invoices-due"),
          explainKey: "invoices_due",
          explainWindowDays: 7,
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
          status: resolveStatusByTarget(completedCount, operations.length ? Math.round(operations.length * 0.95) : 95, "up")
            ?? resolveStatus(undefined, "up", undefined),
          ...resolveKpiNudges("orders-completed"),
          explainKey: "orders_completed",
          explainWindowDays: 7,
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
          deltaValue: 1.1,
          trend: "up",
          goodWhen: "neutral",
          status: resolveStatus("up", "neutral", 1.1),
          ...resolveKpiNudges("balance"),
          explainKey: "balance",
          explainWindowDays: 7,
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
          const trend: KpiTrend | undefined =
            delta === undefined ? undefined : delta > 0 ? "up" : delta < 0 ? "down" : "flat";
          const status =
            resolveStatusByTarget(item.value, item.target ?? undefined, item.good_when) ??
            resolveStatus(trend, item.good_when, delta);
          const nudges = resolveKpiNudges(item.key);
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
            deltaValue: delta ?? undefined,
            trend,
            goodWhen: item.good_when,
            status,
            ...nudges,
            explainKey: item.key,
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
