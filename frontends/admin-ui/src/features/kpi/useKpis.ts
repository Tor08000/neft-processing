import { useEffect, useMemo, useState } from "react";
import type { KpiCardData, KpiHint } from "./types";
import { fetchKpis } from "./api";
import { formatCount, formatDeltaPercent, formatPercent } from "./formatters";

interface KpiResponse {
  kpis: KpiCardData[];
  hints: KpiHint[];
}

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
    }),
    [],
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
        if (isDev && options?.showToast) {
          options.showToast("error", "Mock mode: KPI");
        }
      });
    return () => {
      active = false;
    };
  }, [isDev, options?.showToast]);

  return apiData ?? mockData;
};
