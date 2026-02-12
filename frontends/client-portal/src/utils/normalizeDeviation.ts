import type { RawTripDeviationEvent, TripDeviationEvent } from "../types/logistics";

export function normalizeDeviation(input: RawTripDeviationEvent): TripDeviationEvent | null {
  if (!input?.id || !input?.ts || !input?.type || !input?.severity) {
    return null;
  }

  return {
    id: String(input.id),
    ts: String(input.ts),
    type: input.type,
    severity: input.severity,
    title: input.title ?? "",
    details: input.details ?? null,
    evidence: input.evidence ?? null,
    sla_impact: input.sla_impact ?? null,
  };
}
