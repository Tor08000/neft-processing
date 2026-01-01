export type KpiTrend = "up" | "down" | "flat";
export type KpiGoodWhen = "up" | "down" | "neutral";
export type KpiUnit = "money" | "count" | "percent";
export type KpiProgressMode = "higher-is-better" | "lower-is-better";
export type KpiStatus = "good" | "bad" | "neutral";

export interface KpiCardData {
  id: string;
  title: string;
  value: string | number;
  current?: number;
  subvalue?: string;
  delta?: string;
  deltaValue?: number;
  trend?: KpiTrend;
  goodWhen?: KpiGoodWhen;
  status?: KpiStatus;
  actionLabel?: string;
  actionTo?: string;
  praiseLabel?: string;
  explainKey?: string;
  explainWindowDays?: number;
  unit?: KpiUnit;
  target?: number;
  progress?: number;
  progressMode?: KpiProgressMode;
}

export interface KpiHint {
  id: string;
  label: string;
  icon?: string;
  tone?: "neutral" | "positive" | "warning";
}
