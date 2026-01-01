export type KpiTrend = "up" | "down" | "flat";
export type KpiGoodWhen = "up" | "down" | "neutral";
export type KpiUnit = "money" | "count" | "percent";
export type KpiProgressMode = "higher-is-better" | "lower-is-better";

export interface KpiCardData {
  id: string;
  title: string;
  value: string | number;
  current?: number;
  subvalue?: string;
  delta?: string;
  trend?: KpiTrend;
  goodWhen?: KpiGoodWhen;
  unit?: KpiUnit;
  target?: number;
  progress?: number;
  progressMode?: KpiProgressMode;
  explainKey?: string;
  explainWindowDays?: number;
}

export interface KpiHint {
  id: string;
  label: string;
  icon?: string;
  tone?: "neutral" | "positive" | "warning";
}
