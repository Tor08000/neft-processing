export type ExplainScoreLevel = "clean" | "risky" | "critical";

export type ExplainScore = {
  level: ExplainScoreLevel;
  confidence: number;
  penalty: number;
};

export type StreakState = {
  count: number;
  lastRunAt: string | null;
};

export type AchievementKey =
  | "first_explain"
  | "first_diff"
  | "first_case_created"
  | "ten_explains"
  | "ten_cases_created";

export type AchievementsState = Record<AchievementKey, boolean>;

export type AchievementDefinition = {
  key: AchievementKey;
  label: string;
  description: string;
  icon: string;
};

export type AchievementEvent = "explain_run" | "diff_run" | "case_created";

export type AchievementStats = {
  explainRuns: number;
  diffRuns: number;
  casesCreated: number;
};
