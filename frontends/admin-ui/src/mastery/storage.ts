import type { MasteryCounters, MasteryEvent, MasteryEventType, MasteryState } from "./types";

const EVENTS_STORAGE_KEY = "neft_admin_mastery_events_v1";
const STATE_STORAGE_KEY = "neft_admin_mastery_state_v1";
const MAX_EVENTS = 500;
const MAX_AGE_DAYS = 90;

const DEFAULT_COUNTERS: MasteryCounters = {
  totalExplains: 0,
  totalDiffs: 0,
  totalCasesCreated: 0,
  totalCasesClosed: 0,
  totalActionsApplied: 0,
};

const DEFAULT_STATE: MasteryState = {
  version: 1,
  updatedAt: new Date(0).toISOString(),
  counters: DEFAULT_COUNTERS,
};

const isEventType = (value: string): value is MasteryEventType =>
  [
    "explain_run_success",
    "diff_run_success",
    "case_created",
    "case_closed",
    "action_applied",
  ].includes(value);

const sanitizeEvent = (raw: Partial<MasteryEvent>): MasteryEvent | null => {
  if (!raw.type || !isEventType(raw.type)) return null;
  if (!raw.at || typeof raw.at !== "string") return null;
  const score = raw.score;
  const scoreAfter = raw.score_after;
  return {
    type: raw.type,
    at: raw.at,
    score:
      score && typeof score.level === "string" && typeof score.confidence === "number" && typeof score.penalty === "number"
        ? { level: score.level, confidence: score.confidence, penalty: score.penalty }
        : undefined,
    score_after:
      scoreAfter &&
      typeof scoreAfter.level === "string" &&
      typeof scoreAfter.confidence === "number" &&
      typeof scoreAfter.penalty === "number"
        ? { level: scoreAfter.level, confidence: scoreAfter.confidence, penalty: scoreAfter.penalty }
        : undefined,
    selected_actions_count:
      typeof raw.selected_actions_count === "number" ? raw.selected_actions_count : undefined,
    case_id: typeof raw.case_id === "string" ? raw.case_id : undefined,
  };
};

const sanitizeCounters = (raw: Partial<Record<keyof MasteryCounters, unknown>>): MasteryCounters => ({
  totalExplains: typeof raw.totalExplains === "number" ? raw.totalExplains : DEFAULT_COUNTERS.totalExplains,
  totalDiffs: typeof raw.totalDiffs === "number" ? raw.totalDiffs : DEFAULT_COUNTERS.totalDiffs,
  totalCasesCreated:
    typeof raw.totalCasesCreated === "number" ? raw.totalCasesCreated : DEFAULT_COUNTERS.totalCasesCreated,
  totalCasesClosed:
    typeof raw.totalCasesClosed === "number" ? raw.totalCasesClosed : DEFAULT_COUNTERS.totalCasesClosed,
  totalActionsApplied:
    typeof raw.totalActionsApplied === "number" ? raw.totalActionsApplied : DEFAULT_COUNTERS.totalActionsApplied,
});

export const loadMasteryEvents = (): MasteryEvent[] => {
  if (typeof window === "undefined" || !window.localStorage) return [];
  try {
    const raw = window.localStorage.getItem(EVENTS_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Partial<MasteryEvent>[];
    return (parsed ?? []).map((entry) => sanitizeEvent(entry)).filter((item): item is MasteryEvent => Boolean(item));
  } catch {
    return [];
  }
};

export const saveMasteryEvents = (events: MasteryEvent[]) => {
  if (typeof window === "undefined" || !window.localStorage) return;
  window.localStorage.setItem(EVENTS_STORAGE_KEY, JSON.stringify(events));
};

export const loadMasteryState = (): MasteryState => {
  if (typeof window === "undefined" || !window.localStorage) return DEFAULT_STATE;
  try {
    const raw = window.localStorage.getItem(STATE_STORAGE_KEY);
    if (!raw) return DEFAULT_STATE;
    const parsed = JSON.parse(raw) as Partial<MasteryState>;
    return {
      version: 1,
      updatedAt: typeof parsed.updatedAt === "string" ? parsed.updatedAt : DEFAULT_STATE.updatedAt,
      counters: sanitizeCounters(parsed.counters ?? {}),
    };
  } catch {
    return DEFAULT_STATE;
  }
};

export const saveMasteryState = (state: MasteryState) => {
  if (typeof window === "undefined" || !window.localStorage) return;
  window.localStorage.setItem(STATE_STORAGE_KEY, JSON.stringify(state));
};

export const compactMasteryEvents = (events: MasteryEvent[], now = new Date()): MasteryEvent[] => {
  const cutoff = new Date(now);
  cutoff.setDate(cutoff.getDate() - MAX_AGE_DAYS);
  const filtered = events.filter((event) => {
    const date = new Date(event.at);
    if (Number.isNaN(date.getTime())) return false;
    return date >= cutoff;
  });
  if (filtered.length <= MAX_EVENTS) return filtered;
  return filtered.slice(filtered.length - MAX_EVENTS);
};

export const getDefaultMasteryCounters = (): MasteryCounters => ({ ...DEFAULT_COUNTERS });
