import type { ExplainScore } from "../gamification/types";
import type { MasteryCounters, MasteryEvent, MasteryEventType, MasteryScoreSnapshot } from "./types";
import { compactMasteryEvents, loadMasteryEvents, loadMasteryState, saveMasteryEvents, saveMasteryState } from "./storage";

const applyEventToCounters = (counters: MasteryCounters, event: MasteryEvent): MasteryCounters => {
  const next = { ...counters };
  switch (event.type) {
    case "explain_run_success":
      next.totalExplains += 1;
      break;
    case "diff_run_success":
      next.totalDiffs += 1;
      break;
    case "case_created":
      next.totalCasesCreated += 1;
      break;
    case "case_closed":
      next.totalCasesClosed += 1;
      break;
    case "action_applied":
      next.totalActionsApplied += 1;
      break;
    default:
      break;
  }
  return next;
};

const buildEvent = (type: MasteryEventType, payload?: Partial<MasteryEvent>): MasteryEvent => ({
  type,
  at: new Date().toISOString(),
  ...payload,
});

const toScoreSnapshot = (score?: ExplainScore | null): MasteryScoreSnapshot | undefined =>
  score ? { level: score.level, confidence: score.confidence, penalty: score.penalty } : undefined;

export const appendMasteryEvent = (event: MasteryEvent) => {
  if (typeof window === "undefined" || !window.localStorage) return;
  const events = loadMasteryEvents();
  const updatedEvents = compactMasteryEvents([...events, event]);
  saveMasteryEvents(updatedEvents);

  const state = loadMasteryState();
  const nextCounters = applyEventToCounters(state.counters, event);
  saveMasteryState({ ...state, counters: nextCounters, updatedAt: new Date().toISOString() });
};

export const recordExplainRunSuccess = (score?: ExplainScore | null) => {
  appendMasteryEvent(buildEvent("explain_run_success", { score: toScoreSnapshot(score) }));
};

export const recordDiffRunSuccess = () => {
  appendMasteryEvent(buildEvent("diff_run_success"));
};

export const recordCaseCreated = (options: {
  caseId?: string | null;
  selectedActionsCount?: number;
  score?: ExplainScore | null;
}) => {
  appendMasteryEvent(
    buildEvent("case_created", {
      case_id: options.caseId ?? undefined,
      selected_actions_count: options.selectedActionsCount,
      score: toScoreSnapshot(options.score),
    }),
  );
};

export const recordCaseClosed = (caseId: string, options?: { scoreSnapshot?: ExplainScore | null }) => {
  appendMasteryEvent(
    buildEvent("case_closed", {
      case_id: caseId,
      score: toScoreSnapshot(options?.scoreSnapshot ?? null),
    }),
  );
};

export const recordActionApplied = (options: {
  caseId?: string | null;
  selectedActionsCount?: number;
  scoreBefore?: ExplainScore | null;
  scoreAfter?: ExplainScore | null;
}) => {
  appendMasteryEvent(
    buildEvent("action_applied", {
      case_id: options.caseId ?? undefined,
      selected_actions_count: options.selectedActionsCount,
      score: toScoreSnapshot(options.scoreBefore ?? null),
      score_after: toScoreSnapshot(options.scoreAfter ?? null),
    }),
  );
};
