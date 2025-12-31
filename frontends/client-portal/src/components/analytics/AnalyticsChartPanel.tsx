import type { ReactNode } from "react";

interface AnalyticsChartPanelProps {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
}

export function AnalyticsChartPanel({ title, subtitle, action, children }: AnalyticsChartPanelProps) {
  return (
    <section className="card analytics-panel">
      <div className="card__header">
        <div>
          <h3>{title}</h3>
          {subtitle ? <p className="muted">{subtitle}</p> : null}
        </div>
        {action ? <div className="analytics-panel__action">{action}</div> : null}
      </div>
      {children}
    </section>
  );
}
