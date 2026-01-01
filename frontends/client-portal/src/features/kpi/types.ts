export type KpiTrend = "up" | "down" | "flat";

export interface KpiCardData {
  id: string;
  title: string;
  value: string | number;
  subvalue?: string;
  delta?: string;
  trend?: KpiTrend;
  progress?: number;
  targetLabel?: string;
}

export interface KpiHint {
  id: string;
  label: string;
  icon?: string;
  tone?: "neutral" | "positive" | "warning";
}
