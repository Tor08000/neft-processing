import { useId } from "react";
import type { StreakData } from "../types";

export const StreakWidget = ({ title, description, totalDays, currentDays, history, keepText, breakText }: StreakData) => {
  const tooltipId = useId();
  const dots = Array.from({ length: totalDays }, (_, index) => index < currentDays);
  const historyDots = history?.length ? history : dots;
  const resolvedKeepText = keepText ?? "Продлится, если операции проходят без критических отклонений.";
  const resolvedBreakText = breakText ?? "Сорвется, если появятся критические отклонения или ручные корректировки.";

  return (
    <div className="streak-widget" tabIndex={0} aria-describedby={tooltipId}>
      <div className="streak-widget__title">{title}</div>
      <div className="streak-widget__description">{description}</div>
      <div className="streak-widget__dots" aria-hidden>
        {dots.map((active, index) => (
          <span key={index} className={active ? "streak-dot is-active" : "streak-dot"} />
        ))}
      </div>
      <div className="streak-widget__meta">{currentDays} из {totalDays} дней</div>
      <div className="streak-widget__tooltip" role="tooltip" id={tooltipId}>
        <div className="streak-widget__tooltip-title">История по дням</div>
        <div className="streak-widget__history" aria-hidden>
          {historyDots.map((active, index) => (
            <span key={index} className={active ? "streak-dot is-active" : "streak-dot"} />
          ))}
        </div>
        <div className="streak-widget__tooltip-text">{resolvedKeepText}</div>
        <div className="streak-widget__tooltip-text muted">{resolvedBreakText}</div>
      </div>
    </div>
  );
};

export default StreakWidget;
