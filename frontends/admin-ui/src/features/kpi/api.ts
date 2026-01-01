import { apiGet } from "../../api/client";

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

export const fetchKpiSummary = async (windowDays = 7): Promise<KpiSummary> => {
  return apiGet("/kpi/summary", { window_days: windowDays });
};
