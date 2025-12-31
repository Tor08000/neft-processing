import type { ReactNode } from "react";

interface AnalyticsKpiCardProps {
  label: string;
  value: ReactNode;
  hint?: string;
}

export function AnalyticsKpiCard({ label, value, hint }: AnalyticsKpiCardProps) {
  return (
    <div className="card analytics-kpi">
      <div className="analytics-kpi__label">{label}</div>
      <div className="analytics-kpi__value">{value}</div>
      {hint ? <div className="muted small">{hint}</div> : null}
    </div>
  );
}
