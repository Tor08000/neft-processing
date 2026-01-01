import { CORE_ROOT_API_BASE } from "../../api/base";

export type KpiUnit = "money" | "count" | "percent";
export type KpiGoodWhen = "up" | "down" | "neutral";

export interface KpiSummaryItem {
  key: string;
  title: string;
  value: number;
  unit: KpiUnit;
  delta: number | null;
  good_when: KpiGoodWhen;
  target: number | null;
  progress: number | null;
  meta?: Record<string, unknown> | null;
}

export interface KpiSummary {
  window_days: number;
  as_of: string;
  kpis: KpiSummaryItem[];
}

const buildUrl = (path: string, params?: Record<string, number>) => {
  const url = new URL(`${CORE_ROOT_API_BASE}${path}`);
  if (params) {
    Object.entries(params).forEach(([key, value]) => url.searchParams.set(key, String(value)));
  }
  return url.toString();
};

export const fetchKpiSummary = async (token: string, windowDays = 7): Promise<KpiSummary> => {
  const response = await fetch(buildUrl("/kpi/summary", { window_days: windowDays }), {
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
  });
  if (!response.ok) {
    throw new Error("KPI API unavailable");
  }
  return (await response.json()) as KpiSummary;
};
