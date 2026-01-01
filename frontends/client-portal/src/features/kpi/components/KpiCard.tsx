import { Link } from "react-router-dom";
import type { KpiCardData, KpiGoodWhen, KpiProgressMode, KpiTrend, KpiUnit } from "../types";
import { formatCount, formatMoney, formatPercent } from "../formatters";

const getDeltaTone = (trend?: KpiTrend, goodWhen: KpiGoodWhen = "neutral") => {
  if (goodWhen === "neutral" || !trend || trend === "flat") return "is-neutral";
  if (goodWhen === "up") return trend === "up" ? "is-positive" : "is-negative";
  if (goodWhen === "down") return trend === "down" ? "is-positive" : "is-negative";
  return "is-neutral";
};

const clampProgress = (value?: number) => {
  if (value === undefined) return null;
  return Math.min(1, Math.max(0, value));
};

const getProgressMode = (goodWhen?: KpiGoodWhen, progressMode?: KpiProgressMode) => {
  if (progressMode) return progressMode;
  if (goodWhen === "down") return "lower-is-better";
  return "higher-is-better";
};

const formatUnitValue = (unit: KpiUnit | undefined, value: number) => {
  if (unit === "money") return formatMoney(value);
  if (unit === "percent") return formatPercent(value);
  return formatCount(value);
};

const calculateProgress = (current: number, target: number, mode: KpiProgressMode) => {
  if (mode === "lower-is-better") {
    if (target === 0) return current <= 0 ? 1 : 0;
    if (current <= target) return 1;
    return 1 - (current - target) / target;
  }
  if (target === 0) return current >= 0 ? 1 : 0;
  return current / target;
};

export const KpiCard = ({
  title,
  value,
  current,
  subvalue,
  delta,
  deltaValue,
  trend,
  goodWhen,
  status,
  actionLabel,
  actionTo,
  praiseLabel,
  explainKey,
  unit,
  target,
  progress,
  progressMode,
}: KpiCardData) => {
  const resolvedMode = getProgressMode(goodWhen, progressMode);
  const hasTarget = target !== undefined && target !== null;
  const computedProgress =
    progress ?? (hasTarget && current !== undefined ? calculateProgress(current, target, resolvedMode) : undefined);
  const progressValue = clampProgress(computedProgress);
  const remainingValue =
    hasTarget && current !== undefined
      ? resolvedMode === "lower-is-better"
        ? Math.max(current - target, 0)
        : Math.max(target - current, 0)
      : null;
  const isProblem = status === "bad" || (deltaValue !== undefined && deltaValue < 0);
  const isGood = status === "good" && !isProblem;
  const explainUrl = explainKey ? `/explain?context=kpi&key=${encodeURIComponent(explainKey)}` : null;

  return (
    <div className="kpi-card">
      <div className="kpi-card__header">
        <span className="kpi-card__title">{title}</span>
        {delta !== undefined && delta !== null ? (
          <span className={`kpi-card__delta ${getDeltaTone(trend, goodWhen)}`}>{delta}</span>
        ) : null}
      </div>
      <div className="kpi-card__value">{value}</div>
      {subvalue !== undefined && subvalue !== null ? <div className="kpi-card__subvalue">{subvalue}</div> : null}
      {isProblem && actionLabel ? (
        <div className="kpi-card__callout is-problem">
          {actionTo ? (
            <Link className="kpi-card__link" to={actionTo}>
              {actionLabel}
            </Link>
          ) : (
            <span>{actionLabel}</span>
          )}
          {explainUrl ? (
            <Link className="kpi-card__explain" to={explainUrl}>
              Почему?
            </Link>
          ) : null}
        </div>
      ) : null}
      {isGood && praiseLabel ? <div className="kpi-card__callout is-good">{praiseLabel}</div> : null}
      {hasTarget ? (
        <>
          {progressValue !== null ? (
            <div className="kpi-card__progress">
              <span className="kpi-card__progress-fill" style={{ width: `${progressValue * 100}%` }} />
            </div>
          ) : null}
          <div className="kpi-card__targets">
            <div className="kpi-card__target">Цель: {formatUnitValue(unit, target)}</div>
            {remainingValue !== null ? (
              <div className="kpi-card__target">Осталось: {formatUnitValue(unit, remainingValue)}</div>
            ) : null}
          </div>
        </>
      ) : (
        <div className="kpi-card__target kpi-card__target--empty">Цель не задана</div>
      )}
    </div>
  );
};

export default KpiCard;
