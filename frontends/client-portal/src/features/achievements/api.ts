import type { AchievementBadgeData, StreakData } from "./types";

export interface AchievementsSet {
  badges: AchievementBadgeData[];
  streak: StreakData;
}

export const fetchAchievements = async (): Promise<AchievementsSet> => {
  const response = await fetch("/api/achievements");
  if (!response.ok) {
    throw new Error("Achievements API unavailable");
  }
  const data: AchievementsSet = await response.json();
  if (!data || !Array.isArray(data.badges) || !data.streak) {
    throw new Error("Invalid achievements payload");
  }
  return data;
};
