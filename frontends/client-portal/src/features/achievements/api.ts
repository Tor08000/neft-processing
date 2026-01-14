import { CORE_ROOT_API_BASE, joinUrl } from "../../api/base";

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

const buildUrl = (path: string, params?: Record<string, number>) => {
  const baseOrigin = typeof window !== "undefined" ? window.location.origin : "http://localhost";
  const url = new URL(joinUrl(CORE_ROOT_API_BASE, path), baseOrigin);
  if (params) {
    Object.entries(params).forEach(([key, value]) => url.searchParams.set(key, String(value)));
  }
  return url.toString();
};

export const fetchAchievementsSummary = async (token: string, windowDays = 7): Promise<AchievementsSummary> => {
  const response = await fetch(buildUrl("/achievements/summary", { window_days: windowDays }), {
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
    },
  });
  if (!response.ok) {
    throw new Error("Achievements API unavailable");
  }
  return (await response.json()) as AchievementsSummary;
};
