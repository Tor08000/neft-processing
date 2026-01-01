export type AchievementStatus = "locked" | "unlocked" | "in-progress";

export interface AchievementBadgeData {
  id: string;
  icon: string;
  title: string;
  description: string;
  details?: string;
  status: AchievementStatus;
  progress?: number;
}

export interface StreakData {
  title: string;
  description: string;
  totalDays: number;
  currentDays: number;
  history?: boolean[];
  keepText?: string;
  breakText?: string;
}
