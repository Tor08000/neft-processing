import type { KpiCardData, KpiTrend } from "../types";

const getDeltaTone = (trend?: KpiTrend) => {
  if (trend === "up") return "is-positive";
  if (trend === "down") return "is-negative";
  return "is-neutral";
};

const clampProgress = (value?: number) => {
  if (value === undefined) return null;
  return Math.min(1, Math.max(0, value));
};

export const KpiCard = ({ title, value, subvalue, delta, trend, progress, targetLabel }: KpiCardData) => {
  const progressValue = clampProgress(progress);

  return (
    <div className="kpi-card">
      <div className="kpi-card__header">
        <span className="kpi-card__title">{title}</span>
        {delta ? <span className={`kpi-card__delta ${getDeltaTone(trend)}`}>{delta}</span> : null}
      </div>
      <div className="kpi-card__value">{value}</div>
      {subvalue ? <div className="kpi-card__subvalue">{subvalue}</div> : null}
      {progressValue !== null ? (
        <div className="kpi-card__progress">
          <span className="kpi-card__progress-fill" style={{ width: `${progressValue * 100}%` }} />
        </div>
      ) : null}
      {targetLabel ? <div className="kpi-card__target">{targetLabel}</div> : null}
    </div>
  );
};

export default KpiCard;
