import type { ExplainV2Response } from "../types/explainV2";
import type { ExplainScore } from "./types";

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

const average = (values: number[]) => values.reduce((sum, value) => sum + value, 0) / values.length;

const computeConfidenceFromEvidence = (explain: ExplainV2Response) => {
  const confidences = explain.evidence
    .map((item) => item.confidence)
    .filter((value): value is number => typeof value === "number");

  if (confidences.length) {
    return clamp(average(confidences), 0, 1);
  }

  const evidenceCount = explain.evidence.length;
  const base = 0.25;
  const signal = Math.min(0.7, (evidenceCount / 10) * 0.7);
  return clamp(base + signal, 0, 1);
};

const computePenalty = (explain: ExplainV2Response) => {
  const score = typeof explain.score === "number" ? Math.abs(explain.score) : 0;
  return Math.round(clamp(score, 0, 1) * 100);
};

const resolveScoreLevel = (penalty: number, explain: ExplainV2Response) => {
  if (explain.decision === "DECLINE" || explain.score_band === "block" || penalty >= 80) return "critical";
  if (explain.decision === "REVIEW" || explain.score_band === "high" || explain.score_band === "review") return "risky";
  if (penalty >= 40 || explain.score_band === "medium") return "risky";
  return "clean";
};

export const computeExplainScore = (explain: ExplainV2Response | null): ExplainScore => {
  if (!explain) {
    return { level: "clean", confidence: 0, penalty: 0 };
  }

  const confidence = computeConfidenceFromEvidence(explain);
  const penalty = computePenalty(explain);
  const level = resolveScoreLevel(penalty, explain);

  return { level, confidence, penalty };
};
