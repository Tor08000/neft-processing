import type { ReactNode } from "react";
import { Link } from "react-router-dom";

interface DrilldownLayoutProps {
  title: string;
  subtitle?: string;
  periodLabel: string;
  children: ReactNode;
}

export function DrilldownLayout({ title, subtitle, periodLabel, children }: DrilldownLayoutProps) {
  return (
    <div className="stack analytics-drilldown">
      <section className="card">
        <div className="card__header">
          <div>
            <h2>{title}</h2>
            {subtitle ? <p className="muted">{subtitle}</p> : null}
          </div>
          <Link className="ghost" to="/client/analytics">
            К аналитике
          </Link>
        </div>
        <div className="analytics-drilldown__period">
          <div className="muted small">Период</div>
          <strong>{periodLabel}</strong>
        </div>
      </section>
      {children}
    </div>
  );
}
