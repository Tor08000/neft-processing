import { computeActiveDays, computeConfidenceAverage, computeQualitySignals, deriveCountersFromEvents } from "./metrics";
import type {
  MasteryCounters,
  MasteryEvent,
  MasteryLevelId,
  MasteryRequirement,
  MasterySignals,
  MasterySnapshot,
  MasteryState,
} from "./types";

const LEVEL_LABELS: Record<MasteryLevelId, string> = {
  operator: "Operator",
  senior_operator: "Senior Operator",
  risk_strategist: "Risk Strategist",
};

const formatRemaining = (current: number, target: number, label: string) => {
  const remaining = Math.max(target - current, 0);
  return remaining <= 0 ? label : `${label} · осталось ${remaining}`;
};

const buildRequirement = (
  id: string,
  label: string,
  current: number,
  target: number,
  soft = false,
): MasteryRequirement => ({
  id,
  label,
  current,
  target,
  met: current >= target,
  soft,
});

const calculateProgress = (requirements: MasteryRequirement[]): number => {
  if (!requirements.length) return 1;
  let totalWeight = 0;
  let score = 0;
  requirements.forEach((req) => {
    const weight = req.soft ? 0.5 : 1;
    totalWeight += weight;
    score += Math.min(req.current / req.target, 1) * weight;
  });
  if (totalWeight === 0) return 0;
  return Math.min(score / totalWeight, 1);
};

const buildRecommendations = (requirements: MasteryRequirement[]): string[] => {
  const missing = requirements.filter((req) => !req.met);
  const sorted = [...missing].sort((a, b) => (a.soft === b.soft ? 0 : a.soft ? 1 : -1));
  return sorted.slice(0, 3).map((req) => formatRemaining(req.current, req.target, req.label));
};

const buildMissingRequirements = (requirements: MasteryRequirement[]): string[] =>
  requirements
    .filter((req) => !req.met)
    .map((req) => (req.soft ? `${req.label} (future metric)` : req.label));

const getSignals = (events: MasteryEvent[]): MasterySignals => {
  const quality = computeQualitySignals(events);
  return {
    improvements: quality.improvements,
    cleanAfterActionRate: quality.cleanAfterActionRate,
    actionContexts: quality.actionContexts,
    activeDays: computeActiveDays(events),
    confidenceAvg: computeConfidenceAverage(events),
  };
};

const buildSeniorRequirements = (counters: MasteryCounters, signals: MasterySignals, streakCount: number) => [
  buildRequirement("total_explains", "Run 20 explains", counters.totalExplains, 20),
  buildRequirement("total_diffs", "Run 3 diffs", counters.totalDiffs, 3),
  buildRequirement("total_cases_created", "Create 5 cases", counters.totalCasesCreated, 5),
  buildRequirement("streak", "Maintain streak of 3", streakCount, 3),
  buildRequirement("confidence_avg", "Raise confidence avg to 0.55", signals.confidenceAvg, 0.55),
];

const buildStrategistRequirements = (counters: MasteryCounters, signals: MasterySignals) => [
  buildRequirement("total_explains", "Run 60 explains", counters.totalExplains, 60),
  buildRequirement("total_diffs", "Run 10 diffs", counters.totalDiffs, 10),
  buildRequirement("total_cases_created", "Create 15 cases", counters.totalCasesCreated, 15),
  buildRequirement("improvements", "Achieve 8 improvements", signals.improvements, 8),
  buildRequirement("clean_after_action_rate", "Clean-after-action rate 35%", signals.cleanAfterActionRate, 0.35),
  buildRequirement("total_cases_closed", "Close 5 cases", counters.totalCasesClosed, 5, true),
  buildRequirement("active_days", "Be active 10 days", signals.activeDays, 10, true),
];

const resolveCurrentLevel = (
  counters: MasteryCounters,
  signals: MasterySignals,
  streakCount: number,
): MasteryLevelId => {
  const meetsOperator = counters.totalExplains >= 1;
  const seniorRequirements = buildSeniorRequirements(counters, signals, streakCount);
  const meetsSenior = meetsOperator && seniorRequirements.every((req) => req.met);
  const strategistRequirements = buildStrategistRequirements(counters, signals);
  const meetsStrategist = meetsSenior && strategistRequirements.filter((req) => !req.soft).every((req) => req.met);

  if (meetsStrategist) return "risk_strategist";
  if (meetsSenior) return "senior_operator";
  return "operator";
};

const buildRequirementsForNext = (
  level: MasteryLevelId,
  counters: MasteryCounters,
  signals: MasterySignals,
  streakCount: number,
): MasteryRequirement[] => {
  if (level === "operator") {
    return buildSeniorRequirements(counters, signals, streakCount);
  }
  if (level === "senior_operator") {
    return buildStrategistRequirements(counters, signals);
  }
  return [];
};

const resolveNextLevelId = (level: MasteryLevelId): MasteryLevelId | undefined => {
  if (level === "operator") return "senior_operator";
  if (level === "senior_operator") return "risk_strategist";
  return undefined;
};

export const buildMasterySnapshot = (options: {
  events: MasteryEvent[];
  state?: MasteryState | null;
  streakCount: number;
}): MasterySnapshot => {
  const derivedCounters = deriveCountersFromEvents(options.events);
  const hasStateCounters = Boolean(
    options.state &&
      Object.values(options.state.counters).some((value) => typeof value === "number" && value > 0),
  );
  const counters = hasStateCounters ? options.state!.counters : derivedCounters;
  const signals = getSignals(options.events);
  const level = resolveCurrentLevel(counters, signals, options.streakCount);
  const nextLevelId = resolveNextLevelId(level);
  const requirements = buildRequirementsForNext(level, counters, signals, options.streakCount);
  const progressToNext = nextLevelId ? calculateProgress(requirements) : 1;
  const missingRequirements = buildMissingRequirements(requirements);
  const recommendations = buildRecommendations(requirements);

  return {
    level,
    label: LEVEL_LABELS[level],
    progressToNext,
    nextLevelId,
    nextLabel: nextLevelId ? LEVEL_LABELS[nextLevelId] : undefined,
    requirements,
    missingRequirements,
    recommendations,
    signals,
    counters,
  };
};
