import { useCallback, useEffect, useMemo, useState } from "react";
import type { KpiCardData, KpiHint } from "./types";
import type { KpiSummaryItem, KpiUnit } from "./api";
import { fetchKpiSummary } from "./api";
import { formatCount, formatDeltaPercent, formatMoney, formatPercent } from "./formatters";

interface KpiResponse {
  kpis: KpiCardData[];
  hints: KpiHint[];
  error: string | null;
  isLoading: boolean;
  isMock: boolean;
  reload: () => void;
}

const toastOnce = (key: string, showToast?: (kind: "success" | "error", text: string) => void, text?: string) => {
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
  showToast("error", text ?? "Mock mode");
};

const formatValue = (value: number, unit?: KpiUnit) => {
  if (unit === "percent") {
    return formatPercent(value, 1);
  }
  if (unit === "money") {
    return formatMoney(value);
  }
  return formatCount(value);
};

const buildKpiCard = (item: KpiSummaryItem, windowDays: number): KpiCardData => {
  const delta = item.delta ?? undefined;
  const trend = delta === undefined ? undefined : delta > 0 ? "up" : delta < 0 ? "down" : "flat";
  return {
    id: item.key,
    title: item.title,
    value: formatValue(item.value, item.unit),
    current: item.value,
    subvalue: `за ${windowDays} дней`,
    delta: delta === undefined ? undefined : formatDeltaPercent(delta),
    trend,
    goodWhen: item.good_when,
    unit: item.unit,
    target: item.target ?? undefined,
    progress: item.progress ?? undefined,
  };
};

export const useKpis = (options?: { showToast?: (kind: "success" | "error", text: string) => void }): KpiResponse => {
  const isDev = import.meta.env.DEV;
  const mockData = useMemo<KpiResponse>(
    () => ({
      kpis: [
        {
          id: "billing-errors",
          title: "Billing errors",
          value: formatCount(0),
          current: 0,
          subvalue: "за 7 дней",
          delta: formatDeltaPercent(-12.4),
          trend: "down",
          goodWhen: "down",
          unit: "count",
          target: 0,
        },
        {
          id: "exports-ontime",
          title: "Exports on-time",
          value: formatPercent(95),
          current: 95,
          subvalue: "за 7 дней",
          delta: formatDeltaPercent(1.2),
          trend: "up",
          goodWhen: "up",
          unit: "percent",
          target: 98,
        },
        {
          id: "declines-total",
          title: "Declines total",
          value: formatCount(14),
          current: 14,
          subvalue: "за 7 дней",
          delta: formatDeltaPercent(-6.3),
          trend: "down",
          goodWhen: "down",
          unit: "count",
          target: 10,
        },
        {
          id: "payout-batches",
          title: "Payout batches settled",
          value: formatCount(28),
          current: 28,
          subvalue: "за 7 дней",
          delta: formatDeltaPercent(2.1),
          trend: "up",
          goodWhen: "up",
          unit: "count",
        },
        {
          id: "audit-breaks",
          title: "Audit chain breaks",
          value: formatCount(1),
          current: 1,
          subvalue: "за 7 дней",
          delta: formatDeltaPercent(-50),
          trend: "down",
          goodWhen: "down",
          unit: "count",
          target: 0,
        },
      ],
      hints: [
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
      ],
      error: null,
      isLoading: false,
      isMock: true,
      reload: () => undefined,
    }),
    [],
  );
  const [apiData, setApiData] = useState<KpiResponse | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const reload = useCallback(() => setReloadKey((prev) => prev + 1), []);

  useEffect(() => {
    let active = true;
    setApiData((prev) =>
      prev
        ? { ...prev, isLoading: true, error: null }
        : { kpis: [], hints: [], error: null, isLoading: true, isMock: false, reload },
    );
    fetchKpiSummary()
      .then((data) => {
        if (!active) return;
        const kpis = data.kpis.map((item) => buildKpiCard(item, data.window_days));
        setApiData({ kpis, hints: [], error: null, isLoading: false, isMock: false, reload });
      })
      .catch((err) => {
        if (!active) return;
        if (isDev) {
          toastOnce("admin-kpi", options?.showToast, "Mock mode: KPI");
          setApiData({ ...mockData, reload });
          return;
        }
        const message = err instanceof Error ? err.message : "Не удалось загрузить KPI";
        setApiData({ kpis: [], hints: [], error: message, isLoading: false, isMock: false, reload });
      });
    return () => {
      active = false;
    };
  }, [isDev, mockData, options?.showToast, reload, reloadKey]);

  return apiData ?? mockData;
};
