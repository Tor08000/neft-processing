import type { ReactNode } from "react";

type KpiItem = {
  label: string;
  value: ReactNode;
};

type HeroSummaryCardProps = {
  primary: KpiItem[];
  secondary?: KpiItem[];
  updatedAt: string;
  periodLabel: string;
};

export function HeroSummaryCard({ primary, secondary = [], updatedAt, periodLabel }: HeroSummaryCardProps) {
  return (
    <div className="neftc-glass neftc-hero">
      <div className="neftc-hero__header">
        <div>
          <p className="neftc-hero__eyebrow neftc-text-muted">Сводка</p>
          <h2 className="neftc-hero__title">Ключевые показатели</h2>
        </div>
        <div className="neftc-hero__meta neftc-text-muted">
          <span>Обновлено: {updatedAt}</span>
          <span>Период: {periodLabel}</span>
        </div>
      </div>
      <div className="neftc-hero__kpis">
        {primary.map((item) => (
          <div key={item.label} className="neftc-kpi">
            <div className="neftc-kpi__value">{item.value}</div>
            <div className="neftc-kpi__label">{item.label}</div>
          </div>
        ))}
      </div>
      {secondary.length ? (
        <div className="neftc-hero__secondary">
          {secondary.map((item) => (
            <div key={item.label} className="neftc-kpi neftc-kpi--secondary">
              <div className="neftc-kpi__value">{item.value}</div>
              <div className="neftc-kpi__label">{item.label}</div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
