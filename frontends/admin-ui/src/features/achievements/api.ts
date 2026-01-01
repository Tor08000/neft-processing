import { apiGet } from "../../api/client";

export type AchievementStatus = "locked" | "in_progress" | "unlocked" | "blocked";

export interface AchievementBadgeSummary {
  key: string;
  title: string;
  description: string;
  status: AchievementStatus;
  progress: number | null;
  how_to?: string | null;
  meta?: Record<string, unknown> | null;
}

export interface AchievementStreakSummary {
  key: string;
  title: string;
  current: number;
  target: number;
  history: boolean[];
  status: AchievementStatus;
  how_to?: string | null;
}

export interface AchievementsSummary {
  window_days: number;
  as_of: string;
  badges: AchievementBadgeSummary[];
  streak: AchievementStreakSummary;
}

export const fetchAchievementsSummary = async (windowDays = 7): Promise<AchievementsSummary> => {
  return apiGet("/achievements/summary", { window_days: windowDays });
};
