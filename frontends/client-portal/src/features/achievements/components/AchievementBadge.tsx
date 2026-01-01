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

export const AchievementBadge = ({ icon, title, description, status, progress }: AchievementBadgeData) => {
  const progressValue = clampProgress(progress);

  return (
    <div className={`achievement-badge is-${status}`}>
      <div className="achievement-badge__header">
        <span className="achievement-badge__icon" aria-hidden>
          {icon}
        </span>
        <div>
          <div className="achievement-badge__title">{title}</div>
          <div className="achievement-badge__description">{description}</div>
        </div>
      </div>
      <div className={`achievement-badge__status status-${status}`}>{statusLabels[status]}</div>
      {status === "in-progress" && progressValue !== null ? (
        <div className="achievement-badge__progress">
          <span className="achievement-badge__progress-fill" style={{ width: `${progressValue * 100}%` }} />
        </div>
      ) : null}
    </div>
  );
};

export default AchievementBadge;
