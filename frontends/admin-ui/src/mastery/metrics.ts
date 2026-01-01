import type { MasteryCounters, MasteryEvent, MasterySignals } from "./types";

const PENALTY_IMPROVEMENT_THRESHOLD = 0.1;
const CLEAN_AFTER_ACTION_WINDOW_HOURS = 24;

export const deriveCountersFromEvents = (events: MasteryEvent[]): MasteryCounters =>
  events.reduce(
    (acc, event) => {
      switch (event.type) {
        case "explain_run_success":
          acc.totalExplains += 1;
          break;
        case "diff_run_success":
          acc.totalDiffs += 1;
          break;
        case "case_created":
          acc.totalCasesCreated += 1;
          break;
        case "case_closed":
          acc.totalCasesClosed += 1;
          break;
        case "action_applied":
          acc.totalActionsApplied += 1;
          break;
        default:
          break;
      }
      return acc;
    },
    {
      totalExplains: 0,
      totalDiffs: 0,
      totalCasesCreated: 0,
      totalCasesClosed: 0,
      totalActionsApplied: 0,
    },
  );

const compareLevel = (level?: string) => {
  switch (level) {
    case "clean":
      return 3;
    case "risky":
      return 2;
    case "critical":
      return 1;
    default:
      return 0;
  }
};

const isImproved = (before?: MasteryEvent["score"], after?: MasteryEvent["score"]) => {
  if (!after) return false;
  if (!before) return false;
  if (compareLevel(after.level) > compareLevel(before.level)) return true;
  if (typeof before.penalty === "number" && typeof after.penalty === "number") {
    return before.penalty - after.penalty >= PENALTY_IMPROVEMENT_THRESHOLD;
  }
  return false;
};

const isCleanAfterAction = (before?: MasteryEvent["score"], after?: MasteryEvent["score"]) => {
  if (!after) return false;
  if (after.level === "clean") return true;
  if (!before) return false;
  if (typeof before.penalty === "number" && typeof after.penalty === "number") {
    return before.penalty - after.penalty >= PENALTY_IMPROVEMENT_THRESHOLD;
  }
  return false;
};

export const computeQualitySignals = (events: MasteryEvent[]): Pick<MasterySignals, "improvements" | "cleanAfterActionRate" | "actionContexts"> => {
  if (!events.length) {
    return { improvements: 0, cleanAfterActionRate: 0, actionContexts: 0 };
  }

  const sorted = [...events].sort((a, b) => new Date(a.at).getTime() - new Date(b.at).getTime());
  const windowMs = CLEAN_AFTER_ACTION_WINDOW_HOURS * 60 * 60 * 1000;

  let actionContexts = 0;
  let improvements = 0;
  let cleanAfterActionCount = 0;

  for (let index = 0; index < sorted.length; index += 1) {
    const event = sorted[index];
    if (!event || !["case_created", "action_applied"].includes(event.type)) continue;
    if ((event.selected_actions_count ?? 0) <= 0) continue;
    actionContexts += 1;

    const eventTime = new Date(event.at).getTime();
    if (Number.isNaN(eventTime)) continue;

    const nextExplain = sorted.find(
      (candidate) =>
        candidate.type === "explain_run_success" &&
        new Date(candidate.at).getTime() > eventTime &&
        new Date(candidate.at).getTime() - eventTime <= windowMs,
    );

    if (!nextExplain) continue;
    if (isImproved(event.score, nextExplain.score)) {
      improvements += 1;
    }
    if (isCleanAfterAction(event.score, nextExplain.score)) {
      cleanAfterActionCount += 1;
    }
  }

  return {
    improvements,
    cleanAfterActionRate: actionContexts > 0 ? cleanAfterActionCount / actionContexts : 0,
    actionContexts,
  };
};

export const computeConfidenceAverage = (events: MasteryEvent[]): number => {
  const scored = events.filter((event) => event.type === "explain_run_success" && event.score);
  if (!scored.length) return 0;
  const total = scored.reduce((sum, event) => sum + (event.score?.confidence ?? 0), 0);
  return total / scored.length;
};

export const computeActiveDays = (events: MasteryEvent[]): number => {
  const days = new Set<string>();
  events.forEach((event) => {
    if (event.type !== "explain_run_success") return;
    const date = new Date(event.at);
    if (Number.isNaN(date.getTime())) return;
    days.add(date.toISOString().slice(0, 10));
  });
  return days.size;
};
