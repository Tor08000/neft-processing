import { describe, expect, it } from "vitest";
import { unlockAchievements, updateAchievementStats } from "./achievements";

const baseStats = { explainRuns: 0, diffRuns: 0, casesCreated: 0 };
const baseAchievements = {
  first_explain: false,
  first_diff: false,
  first_case_created: false,
  ten_explains: false,
  ten_cases_created: false,
};

describe("achievements", () => {
  it("unlocks first diff", () => {
    const stats = updateAchievementStats(baseStats, "diff_run");
    const achievements = unlockAchievements(baseAchievements, stats);
    expect(achievements.first_diff).toBe(true);
  });

  it("unlocks first case created", () => {
    const stats = updateAchievementStats(baseStats, "case_created");
    const achievements = unlockAchievements(baseAchievements, stats);
    expect(achievements.first_case_created).toBe(true);
  });

  it("unlocks ten explains", () => {
    const stats = { ...baseStats, explainRuns: 10 };
    const achievements = unlockAchievements(baseAchievements, stats);
    expect(achievements.ten_explains).toBe(true);
  });
});
