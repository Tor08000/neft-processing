import { request } from "./http";
import type {
  SupportRequestCreatePayload,
  SupportRequestDetail,
  SupportRequestItem,
  SupportRequestListResponse,
  SupportRequestPriority,
  SupportRequestScopeType,
  SupportRequestStatus,
  SupportRequestSubjectType,
} from "../types/support";

type CaseKind = "order" | "support" | "dispute" | "incident" | "operation" | "invoice" | "kpi" | "fleet" | "booking";
type CaseStatus = "TRIAGE" | "IN_PROGRESS" | "WAITING" | "RESOLVED" | "CLOSED";
type CasePriority = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

interface CaseItem {
  id: string;
  tenant_id: number;
  kind: CaseKind;
  queue?: string | null;
  entity_type?: string | null;
  entity_id?: string | null;
  title: string;
  description?: string | null;
  status: CaseStatus;
  priority: CasePriority;
  created_by?: string | null;
  client_id?: string | null;
  partner_id?: string | null;
  case_source_ref_type?: string | null;
  case_source_ref_id?: string | null;
  first_response_due_at?: string | null;
  resolve_due_at?: string | null;
  created_at: string;
  updated_at: string;
}

interface CaseListResponse {
  items: CaseItem[];
  total: number;
  limit: number;
  next_cursor?: string | null;
}

interface CaseDetailsResponse {
  case: CaseItem;
  timeline: Array<{ status: CaseStatus; occurred_at: string }>;
}
export interface SupportRequestFilters {
  status?: string;
  subject_type?: string;
  from?: string;
  to?: string;
  limit?: number;
  offset?: number;
}

const SUPPORT_CASE_KINDS = new Set<CaseKind>(["order", "support", "dispute", "incident"]);

const SUPPORT_TO_CASE_STATUS: Record<SupportRequestStatus, CaseStatus> = {
  OPEN: "TRIAGE",
  IN_PROGRESS: "IN_PROGRESS",
  WAITING: "WAITING",
  RESOLVED: "RESOLVED",
  CLOSED: "CLOSED",
};

const CASE_TO_SUPPORT_STATUS: Record<CaseStatus, SupportRequestStatus> = {
  TRIAGE: "OPEN",
  IN_PROGRESS: "IN_PROGRESS",
  WAITING: "WAITING",
  RESOLVED: "RESOLVED",
  CLOSED: "CLOSED",
};

const CASE_TO_SUPPORT_PRIORITY: Record<CasePriority, SupportRequestPriority> = {
  LOW: "LOW",
  MEDIUM: "NORMAL",
  HIGH: "HIGH",
  CRITICAL: "HIGH",
};

const SUBJECT_TO_CASE_KIND: Record<SupportRequestSubjectType, CaseKind> = {
  ORDER: "order",
  DOCUMENT: "incident",
  PAYOUT: "dispute",
  SETTLEMENT: "dispute",
  INTEGRATION: "support",
  OTHER: "support",
};

const caseKindToSubjectType = (kind: CaseKind, entityType?: string | null): SupportRequestSubjectType => {
  const normalized = (entityType ?? "").trim().toUpperCase();
  if (normalized === "ORDER") return "ORDER";
  if (normalized === "DOCUMENT") return "DOCUMENT";
  if (normalized === "PAYOUT") return "PAYOUT";
  if (normalized === "SETTLEMENT") return "SETTLEMENT";
  if (normalized === "INTEGRATION") return "INTEGRATION";
  if (kind === "order") return "ORDER";
  if (kind === "dispute") return "PAYOUT";
  if (kind === "incident") return "DOCUMENT";
  return "OTHER";
};

const isSupportCase = (item: CaseItem) =>
  SUPPORT_CASE_KINDS.has(item.kind) ||
  item.case_source_ref_type === "SUPPORT_REQUEST" ||
  item.case_source_ref_type === "SUPPORT_TICKET";

const withinDateRange = (value: string, from?: string, to?: string) => {
  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return false;
  if (from) {
    const fromTimestamp = new Date(`${from}T00:00:00Z`).getTime();
    if (!Number.isNaN(fromTimestamp) && timestamp < fromTimestamp) {
      return false;
    }
  }
  if (to) {
    const toTimestamp = new Date(`${to}T23:59:59Z`).getTime();
    if (!Number.isNaN(toTimestamp) && timestamp > toTimestamp) {
      return false;
    }
  }
  return true;
};

const mapCaseToSupportRequest = (item: CaseItem): SupportRequestItem => {
  const scopeType: SupportRequestScopeType = item.partner_id ? "PARTNER" : "CLIENT";
  return {
    id: item.id,
    tenant_id: item.tenant_id,
    client_id: item.client_id ?? null,
    partner_id: item.partner_id ?? null,
    created_by_user_id: item.created_by ?? null,
    scope_type: scopeType,
    subject_type: caseKindToSubjectType(item.kind, item.entity_type),
    subject_id: item.entity_id ?? null,
    correlation_id: null,
    event_id: null,
    title: item.title,
    description: item.description ?? "",
    status: CASE_TO_SUPPORT_STATUS[item.status],
    priority: CASE_TO_SUPPORT_PRIORITY[item.priority],
    created_at: item.created_at,
    updated_at: item.updated_at,
    resolved_at: item.status === "RESOLVED" || item.status === "CLOSED" ? item.updated_at : null,
    case_kind: item.kind,
    case_queue: item.queue ?? null,
    case_source_ref_type: item.case_source_ref_type ?? null,
    case_source_ref_id: item.case_source_ref_id ?? null,
    case_first_response_due_at: item.first_response_due_at ?? null,
    case_resolve_due_at: item.resolve_due_at ?? null,
  };
};

const mapCaseDetailsToSupportRequest = (
  payload: CaseDetailsResponse,
  overrides?: Partial<Pick<SupportRequestDetail, "correlation_id" | "event_id">>,
): SupportRequestDetail => ({
  ...mapCaseToSupportRequest(payload.case),
  correlation_id: overrides?.correlation_id ?? null,
  event_id: overrides?.event_id ?? null,
  timeline: (payload.timeline ?? []).map((event) => ({
    status: CASE_TO_SUPPORT_STATUS[event.status],
    occurred_at: event.occurred_at,
  })),
});

export const createSupportRequest = async (payload: SupportRequestCreatePayload, token: string) => {
  const created = await request<CaseItem>(
    "/cases",
    {
      method: "POST",
      body: JSON.stringify({
        kind: SUBJECT_TO_CASE_KIND[payload.subject_type],
        entity_type: payload.subject_type,
        entity_id: payload.subject_id ?? null,
        title: payload.title,
        description: payload.description,
        priority: "MEDIUM",
      }),
    },
    { token, base: "core_root" },
  );

  return {
    ...mapCaseToSupportRequest(created),
    correlation_id: payload.correlation_id ?? null,
    event_id: payload.event_id ?? null,
    timeline: created.created_at
      ? [
          {
            status: CASE_TO_SUPPORT_STATUS[created.status],
            occurred_at: created.created_at,
          },
        ]
      : [],
  } satisfies SupportRequestDetail;
};

export const fetchSupportRequests = async (token: string, filters: SupportRequestFilters = {}) => {
  const offset = filters.offset ?? 0;
  const limit = filters.limit ?? 50;
  const requestedLimit = Math.min(Math.max(limit + offset, 100), 200);
  const search = new URLSearchParams();
  if (filters.status) search.set("status", SUPPORT_TO_CASE_STATUS[filters.status as SupportRequestStatus]);
  if (filters.subject_type) search.set("entity_type", filters.subject_type);
  search.set("limit", String(requestedLimit));
  const query = search.toString();
  const path = query ? `/cases?${query}` : "/cases";
  const response = await request<CaseListResponse>(path, { method: "GET" }, { token, base: "core_root" });
  const filtered = (response.items ?? [])
    .filter(isSupportCase)
    .filter((item) => withinDateRange(item.created_at, filters.from, filters.to));
  const paged = filtered.slice(offset, offset + limit).map(mapCaseToSupportRequest);
  return {
    items: paged,
    total: filtered.length,
    limit,
    offset,
  } satisfies SupportRequestListResponse;
};

export const fetchSupportRequest = async (requestId: string, token: string) => {
  const response = await request<CaseDetailsResponse>(`/cases/${requestId}`, { method: "GET" }, { token, base: "core_root" });
  return mapCaseDetailsToSupportRequest(response);
};
