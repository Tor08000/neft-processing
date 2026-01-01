import type { StreakData } from "../types";

export const StreakWidget = ({ title, description, totalDays, currentDays }: StreakData) => {
  const dots = Array.from({ length: totalDays }, (_, index) => index < currentDays);

  return (
    <div className="streak-widget">
      <div className="streak-widget__title">{title}</div>
      <div className="streak-widget__description">{description}</div>
      <div className="streak-widget__dots" aria-hidden>
        {dots.map((active, index) => (
          <span key={index} className={active ? "streak-dot is-active" : "streak-dot"} />
        ))}
      </div>
      <div className="streak-widget__meta">{currentDays} из {totalDays} дней</div>
    </div>
  );
};

export default StreakWidget;
