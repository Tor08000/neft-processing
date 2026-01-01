import type {
  AchievementDefinition,
  AchievementEvent,
  AchievementKey,
  AchievementStats,
  AchievementsState,
} from "./types";

const ACHIEVEMENTS_STORAGE_KEY = "explain_achievements";
const STATS_STORAGE_KEY = "explain_achievement_stats";

const DEFAULT_ACHIEVEMENTS: AchievementsState = {
  first_explain: false,
  first_diff: false,
  first_case_created: false,
  ten_explains: false,
  ten_cases_created: false,
};

const DEFAULT_STATS: AchievementStats = {
  explainRuns: 0,
  diffRuns: 0,
  casesCreated: 0,
};

export const ACHIEVEMENT_DEFINITIONS: AchievementDefinition[] = [
  {
    key: "first_explain",
    label: "First Explain",
    description: "Выполнен первый explain-run",
    icon: "🏁",
  },
  {
    key: "first_diff",
    label: "First Diff",
    description: "Выполнено первое сравнение diff",
    icon: "🔀",
  },
  {
    key: "first_case_created",
    label: "First Case Created",
    description: "Создан первый кейс из Explain",
    icon: "🗂",
  },
  {
    key: "ten_explains",
    label: "10 Explains",
    description: "Выполнено 10 explain-run",
    icon: "🧠",
  },
  {
    key: "ten_cases_created",
    label: "10 Cases Created",
    description: "Создано 10 кейсов из Explain",
    icon: "🧾",
  },
];

export const updateAchievementStats = (previous: AchievementStats, event: AchievementEvent): AchievementStats => {
  switch (event) {
    case "explain_run":
      return { ...previous, explainRuns: previous.explainRuns + 1 };
    case "diff_run":
      return { ...previous, diffRuns: previous.diffRuns + 1 };
    case "case_created":
      return { ...previous, casesCreated: previous.casesCreated + 1 };
    default:
      return previous;
  }
};

export const unlockAchievements = (previous: AchievementsState, stats: AchievementStats): AchievementsState => {
  const next: AchievementsState = { ...previous };

  if (stats.explainRuns >= 1) next.first_explain = true;
  if (stats.diffRuns >= 1) next.first_diff = true;
  if (stats.casesCreated >= 1) next.first_case_created = true;
  if (stats.explainRuns >= 10) next.ten_explains = true;
  if (stats.casesCreated >= 10) next.ten_cases_created = true;

  return next;
};

const sanitizeAchievements = (raw: Partial<Record<AchievementKey, unknown>>): AchievementsState => {
  const next = { ...DEFAULT_ACHIEVEMENTS };
  (Object.keys(next) as AchievementKey[]).forEach((key) => {
    if (typeof raw[key] === "boolean") {
      next[key] = raw[key] as boolean;
    }
  });
  return next;
};

const sanitizeStats = (raw: Partial<Record<keyof AchievementStats, unknown>>): AchievementStats => ({
  explainRuns: typeof raw.explainRuns === "number" ? raw.explainRuns : DEFAULT_STATS.explainRuns,
  diffRuns: typeof raw.diffRuns === "number" ? raw.diffRuns : DEFAULT_STATS.diffRuns,
  casesCreated: typeof raw.casesCreated === "number" ? raw.casesCreated : DEFAULT_STATS.casesCreated,
});

export const loadAchievementsState = (): AchievementsState => {
  if (typeof window === "undefined" || !window.localStorage) return DEFAULT_ACHIEVEMENTS;
  try {
    const raw = window.localStorage.getItem(ACHIEVEMENTS_STORAGE_KEY);
    if (!raw) return DEFAULT_ACHIEVEMENTS;
    const parsed = JSON.parse(raw) as Partial<Record<AchievementKey, unknown>>;
    return sanitizeAchievements(parsed ?? {});
  } catch {
    return DEFAULT_ACHIEVEMENTS;
  }
};

export const saveAchievementsState = (state: AchievementsState) => {
  if (typeof window === "undefined" || !window.localStorage) return;
  window.localStorage.setItem(ACHIEVEMENTS_STORAGE_KEY, JSON.stringify(state));
};

export const loadAchievementStats = (): AchievementStats => {
  if (typeof window === "undefined" || !window.localStorage) return DEFAULT_STATS;
  try {
    const raw = window.localStorage.getItem(STATS_STORAGE_KEY);
    if (!raw) return DEFAULT_STATS;
    const parsed = JSON.parse(raw) as Partial<Record<keyof AchievementStats, unknown>>;
    return sanitizeStats(parsed ?? {});
  } catch {
    return DEFAULT_STATS;
  }
};

export const saveAchievementStats = (stats: AchievementStats) => {
  if (typeof window === "undefined" || !window.localStorage) return;
  window.localStorage.setItem(STATS_STORAGE_KEY, JSON.stringify(stats));
};
