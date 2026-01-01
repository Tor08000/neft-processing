import { apiGet, apiPost } from "./client";

export type CaseStatus = "OPEN" | "IN_PROGRESS" | "CLOSED";
export type CasePriority = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type CaseItem = {
  id: string;
  status: CaseStatus;
  priority?: CasePriority;
  title?: string;
  note?: string;
  created_at: string;
  created_by?: string;
  updated_at?: string;
  closed_at?: string | null;
  closed_by?: string | null;
  kind?: string | null;
  snapshots?: unknown;
};

export type CaseSnapshot = {
  id: string;
  explain_snapshot?: unknown;
  diff_snapshot?: unknown | null;
  selected_actions?: { code: string; what_if?: unknown | null }[] | null;
  note?: string | null;
  created_at: string;
};

export type CaseEventType =
  | "CASE_CREATED"
  | "STATUS_CHANGED"
  | "CASE_CLOSED"
  | "NOTE_UPDATED"
  | "ACTIONS_APPLIED"
  | "EXPORT_CREATED";

export type CaseFieldChange = { field: string; from: unknown; to: unknown };

export type CaseEvent = {
  id: string;
  at: string;
  type: CaseEventType;
  actor?: { id?: string; email?: string; name?: string } | null;
  request_id?: string | null;
  trace_id?: string | null;
  meta?: {
    changes?: CaseFieldChange[];
    reason?: string | null;
    export_ref?: {
      kind: "explain_export" | "diff_export" | "case_export";
      id: string;
      url?: string | null;
    } | null;
    selected_actions_count?: number | null;
  } | null;
};

export type CaseListResponse = {
  items: CaseItem[];
  total?: number;
  limit?: number;
  next_cursor?: string | null;
};

export type CaseDetailsResponse = {
  case: CaseItem;
  latest_snapshot?: CaseSnapshot | null;
  snapshots?: CaseSnapshot[] | null;
};

export type CaseClosePayload = {
  resolution_note: string;
  resolution_code?: string | null;
};

export type CaseEventsResponse = {
  items: CaseEvent[];
  next_cursor?: string | null;
  unavailable?: boolean;
};

type CaseExportRef = NonNullable<NonNullable<CaseEvent["meta"]>["export_ref"]>;

export class NotAvailableError extends Error {
  constructor(message = "Not available in this environment") {
    super(message);
    this.name = "NotAvailableError";
  }
}

const isNotAvailableMessage = (message?: string) => Boolean(message && /HTTP (404|501)\b/.test(message));

const ensureAvailability = (error: unknown): never => {
  if (error instanceof NotAvailableError) {
    throw error;
  }
  if (error instanceof Error && isNotAvailableMessage(error.message)) {
    throw new NotAvailableError();
  }
  throw error;
};

export const isNotAvailableError = (error: unknown): boolean => {
  if (error instanceof NotAvailableError) return true;
  if (error instanceof Error) {
    return isNotAvailableMessage(error.message);
  }
  return false;
};

export const fetchAdminCases = async (params: {
  status?: CaseStatus | string;
  priority?: CasePriority | string;
  q?: string;
  limit?: number;
  cursor?: string | null;
}): Promise<CaseListResponse> => {
  try {
    return await apiGet("/api/admin/cases", params);
  } catch (error) {
    return ensureAvailability(error);
  }
};

export const fetchAdminCaseDetails = async (caseId: string): Promise<CaseDetailsResponse> => {
  try {
    return await apiGet(`/api/admin/cases/${caseId}`);
  } catch (error) {
    return ensureAvailability(error);
  }
};

export const closeAdminCase = async (caseId: string, payload: CaseClosePayload): Promise<CaseItem | void> => {
  try {
    return await apiPost(`/api/admin/cases/${caseId}/close`, payload);
  } catch (error) {
    return ensureAvailability(error);
  }
};

export const updateAdminCaseStatus = async (caseId: string, status: CaseStatus): Promise<CaseItem | void> => {
  try {
    return await apiPost(`/api/admin/cases/${caseId}/status`, { status });
  } catch (error) {
    return ensureAvailability(error);
  }
};

const EVENT_TYPES: CaseEventType[] = [
  "CASE_CREATED",
  "STATUS_CHANGED",
  "CASE_CLOSED",
  "NOTE_UPDATED",
  "ACTIONS_APPLIED",
  "EXPORT_CREATED",
];

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null;

const normalizeString = (value: unknown): string | null => (typeof value === "string" ? value : null);

const normalizeEventType = (value: unknown): CaseEventType | null => {
  if (typeof value !== "string") return null;
  const upper = value.toUpperCase();
  return EVENT_TYPES.includes(upper as CaseEventType) ? (upper as CaseEventType) : null;
};

const normalizeActor = (value: unknown): CaseEvent["actor"] => {
  if (!value) return null;
  if (typeof value === "string") {
    return { email: value };
  }
  if (!isRecord(value)) return null;
  const id = normalizeString(value.id);
  const email = normalizeString(value.email);
  const name = normalizeString(value.name);
  if (!id && !email && !name) return null;
  return { id: id ?? undefined, email: email ?? undefined, name: name ?? undefined };
};

const normalizeChanges = (value: unknown): CaseFieldChange[] | undefined => {
  if (!Array.isArray(value)) return undefined;
  const changes = value
    .map((entry) => {
      if (!isRecord(entry)) return null;
      const field = normalizeString(entry.field);
      if (!field) return null;
      return { field, from: entry.from, to: entry.to };
    })
    .filter((entry): entry is CaseFieldChange => Boolean(entry));
  return changes.length ? changes : undefined;
};

const normalizeExportRef = (value: unknown): CaseExportRef | null => {
  if (!isRecord(value)) return null;
  const kindValue = normalizeString(value.kind);
  if (!kindValue) return null;
  const kind = ["explain_export", "diff_export", "case_export"].includes(kindValue)
    ? (kindValue as "explain_export" | "diff_export" | "case_export")
    : null;
  const id = normalizeString(value.id);
  if (!kind || !id) return null;
  const url = normalizeString(value.url);
  return { kind, id, url: url ?? undefined };
};

const normalizeCaseEvent = (value: unknown, index: number): CaseEvent | null => {
  if (!isRecord(value)) return null;
  const idValue = value.id ?? `evt_${index}`;
  const id = typeof idValue === "string" ? idValue : String(idValue);
  const at = normalizeString(value.at) ?? normalizeString(value.created_at);
  const type = normalizeEventType(value.type);
  if (!at || !type) return null;
  const actor = normalizeActor(value.actor ?? value.user ?? value.author);
  const requestId = normalizeString(value.request_id ?? value.requestId);
  const traceId = normalizeString(value.trace_id ?? value.traceId);
  const rawMeta = isRecord(value.meta) ? value.meta : isRecord(value.metadata) ? value.metadata : undefined;
  const changes = normalizeChanges(rawMeta?.changes);
  const exportRef = normalizeExportRef(rawMeta?.export_ref ?? rawMeta?.exportRef);
  const reason = normalizeString(rawMeta?.reason ?? value.note);
  const selectedActionsCount =
    typeof rawMeta?.selected_actions_count === "number" ? rawMeta.selected_actions_count : null;
  const meta =
    changes || exportRef || reason || selectedActionsCount !== null
      ? {
          changes,
          reason,
          export_ref: exportRef,
          selected_actions_count: selectedActionsCount,
        }
      : null;
  return {
    id,
    at,
    type,
    actor,
    request_id: requestId,
    trace_id: traceId,
    meta,
  };
};

const isCaseEvent = (event: CaseEvent | null): event is CaseEvent => event !== null;

const normalizeEventsResponse = (payload: unknown): { items: CaseEvent[]; next_cursor?: string | null } => {
  if (Array.isArray(payload)) {
    return { items: payload.map((item, index) => normalizeCaseEvent(item, index)).filter(isCaseEvent) };
  }
  if (isRecord(payload)) {
    const rawItems = Array.isArray(payload.items)
      ? payload.items
      : Array.isArray(payload.events)
        ? payload.events
        : [];
    const nextCursor = normalizeString(payload.next_cursor);
    return {
      items: rawItems.map((item, index) => normalizeCaseEvent(item, index)).filter(isCaseEvent),
      next_cursor: nextCursor ?? undefined,
    };
  }
  return { items: [] };
};

export const listCaseEvents = async (
  caseId: string,
  params?: { cursor?: string | null; limit?: number },
): Promise<CaseEventsResponse> => {
  try {
    const response = await apiGet(`/api/admin/cases/${caseId}/events`, params);
    return normalizeEventsResponse(response);
  } catch (error) {
    if (isNotAvailableError(error)) {
      return { items: [], unavailable: true };
    }
    throw error;
  }
};
