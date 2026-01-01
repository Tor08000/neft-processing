import type { KpiCardData, KpiHint } from "./types";

export interface KpiSet {
  kpis: KpiCardData[];
  hints: KpiHint[];
}

export const fetchKpis = async (): Promise<KpiSet> => {
  const response = await fetch("/api/kpi");
  if (!response.ok) {
    throw new Error("KPI API unavailable");
  }
  const data: KpiSet = await response.json();
  if (!data || !Array.isArray(data.kpis) || !Array.isArray(data.hints)) {
    throw new Error("Invalid KPI payload");
  }
  return data;
};
