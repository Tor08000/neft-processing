import { useState } from "react";
import type { AchievementBadgeData } from "../types";

const statusLabels: Record<AchievementBadgeData["status"], string> = {
  unlocked: "Достигнуто",
  locked: "Заблокировано",
  "in-progress": "В прогрессе",
};

const clampProgress = (value?: number) => {
  if (value === undefined) return null;
  return Math.min(1, Math.max(0, value));
};

export const AchievementBadge = ({ icon, title, description, details, status, progress }: AchievementBadgeData) => {
  const progressValue = clampProgress(progress);
  const detailsText = details ?? description;
  const [isExpanded, setIsExpanded] = useState(status === "locked");
  const showToggle = Boolean(detailsText) && status !== "locked";
  const remainingPercent =
    status === "in-progress" && progressValue !== null ? Math.max(0, Math.round((1 - progressValue) * 100)) : null;

  return (
    <div className={`achievement-badge is-${status}`}>
      <div className="achievement-badge__header">
        <span className="achievement-badge__icon" aria-hidden>
          {icon}
        </span>
        <div className="achievement-badge__content">
          <div className="achievement-badge__title-row">
            <div className="achievement-badge__title">{title}</div>
            {showToggle ? (
              <button
                className="achievement-badge__action"
                type="button"
                title="Как получить"
                aria-label="Как получить"
                aria-expanded={isExpanded}
                onClick={() => setIsExpanded((prev) => !prev)}
              >
                ?
              </button>
            ) : null}
          </div>
          <div className="achievement-badge__description">{description}</div>
        </div>
      </div>
      <div className={`achievement-badge__status status-${status}`}>{statusLabels[status]}</div>
      {isExpanded ? (
        <div className="achievement-badge__details">
          {status === "locked" ? "Условие: " : null}
          {detailsText}
        </div>
      ) : null}
      {status === "in-progress" && progressValue !== null ? (
        <>
          <div className="achievement-badge__progress">
            <span className="achievement-badge__progress-fill" style={{ width: `${progressValue * 100}%` }} />
          </div>
          {remainingPercent !== null ? (
            <div className="achievement-badge__remaining">Осталось: {remainingPercent}%</div>
          ) : null}
        </>
      ) : null}
    </div>
  );
};

export default AchievementBadge;
