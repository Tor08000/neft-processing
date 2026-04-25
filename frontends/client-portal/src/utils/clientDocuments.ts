import type { ClientDocumentListItem } from "../api/client/documents";
import { getEdoTone as getLegacyEdoTone } from "./documents";

export const PERIOD_FALLBACK_KEY = "__NO_PERIOD__";

const ATTENTION_EDO_STATES = new Set(["FAILED", "REJECTED"]);

export function getAckLikeState(item: ClientDocumentListItem): "SIGNED" | "REQUESTED" | null {
  if (item.ack_at) return "SIGNED";
  const direction = item.direction.toLowerCase();
  if (direction === "inbound" || item.action_code === "SIGN") return "REQUESTED";
  return null;
}

export function hasLegacyLikeAttention(item: ClientDocumentListItem): boolean {
  const edoStatus = item.edo_status?.toUpperCase();
  return getAckLikeState(item) === "REQUESTED" || ATTENTION_EDO_STATES.has(edoStatus ?? "") || item.requires_action === true;
}

export function getEdoTone(item: ClientDocumentListItem): "success" | "warning" | "error" | "neutral" {
  return getLegacyEdoTone(item.edo_status);
}

export function getPeriodGroupKey(item: ClientDocumentListItem): string {
  return item.period_from ? item.period_from.slice(0, 7) : PERIOD_FALLBACK_KEY;
}

export function formatPeriodGroupLabel(groupKey: string): string {
  return groupKey === PERIOD_FALLBACK_KEY ? "Без периода" : groupKey;
}
