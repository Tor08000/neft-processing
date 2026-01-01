import type { StreakState } from "./types";

const STORAGE_KEY = "explain_streak";
const DEFAULT_STREAK: StreakState = { count: 0, lastRunAt: null };

export const updateStreak = (previous: StreakState | null, now: Date, windowMs = 24 * 60 * 60 * 1000): StreakState => {
  const prevState = previous ?? DEFAULT_STREAK;
  const lastRunAt = prevState.lastRunAt ? new Date(prevState.lastRunAt) : null;

  if (!lastRunAt || Number.isNaN(lastRunAt.getTime())) {
    return { count: 1, lastRunAt: now.toISOString() };
  }

  const delta = now.getTime() - lastRunAt.getTime();
  const nextCount = delta <= windowMs ? prevState.count + 1 : 1;

  return { count: nextCount, lastRunAt: now.toISOString() };
};

export const loadStreakState = (): StreakState => {
  if (typeof window === "undefined" || !window.localStorage) return DEFAULT_STREAK;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_STREAK;
    const parsed = JSON.parse(raw) as StreakState;
    if (typeof parsed.count !== "number") return DEFAULT_STREAK;
    return { count: parsed.count, lastRunAt: parsed.lastRunAt ?? null };
  } catch {
    return DEFAULT_STREAK;
  }
};

export const saveStreakState = (state: StreakState) => {
  if (typeof window === "undefined" || !window.localStorage) return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
};
