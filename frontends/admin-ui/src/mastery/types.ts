export type MasteryLevelId = "operator" | "senior_operator" | "risk_strategist";

export type MasteryScoreLevel = "clean" | "risky" | "critical";

export type MasteryEventType =
  | "explain_run_success"
  | "diff_run_success"
  | "case_created"
  | "case_closed"
  | "action_applied";

export type MasteryScoreSnapshot = {
  level: MasteryScoreLevel;
  confidence: number;
  penalty: number;
};

export type MasteryEvent = {
  type: MasteryEventType;
  at: string;
  score?: MasteryScoreSnapshot;
  selected_actions_count?: number;
  case_id?: string;
};

export type MasteryCounters = {
  totalExplains: number;
  totalDiffs: number;
  totalCasesCreated: number;
  totalCasesClosed: number;
  totalActionsApplied: number;
};

export type MasteryState = {
  version: 1;
  updatedAt: string;
  counters: MasteryCounters;
};

export type MasterySignals = {
  improvements: number;
  cleanAfterActionRate: number;
  actionContexts: number;
  activeDays: number;
  confidenceAvg: number;
};

export type MasteryRequirement = {
  id: string;
  label: string;
  current: number;
  target: number;
  met: boolean;
  soft?: boolean;
};

export type MasterySnapshot = {
  level: MasteryLevelId;
  label: string;
  progressToNext: number;
  nextLevelId?: MasteryLevelId;
  nextLabel?: string;
  requirements: MasteryRequirement[];
  missingRequirements: string[];
  recommendations: string[];
  signals: MasterySignals;
  counters: MasteryCounters;
};
