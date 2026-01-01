import type { AuthSession } from "./types";
import { request } from "./http";
import type { CaseDetailsResponse, CaseListResponse } from "../types/cases";

export function fetchCases(
  user: AuthSession | null,
  params: { status?: string; kind?: string; priority?: string; q?: string } = {},
): Promise<CaseListResponse> {
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  if (params.kind) query.set("kind", params.kind);
  if (params.priority) query.set("priority", params.priority);
  if (params.q) query.set("q", params.q);
  const suffix = query.toString();
  const path = suffix ? `/cases?${suffix}` : "/cases";
  return request<CaseListResponse>(path, { method: "GET" }, { token: user?.token ?? null, base: "core_root" });
}

export function fetchCaseDetails(caseId: string, user: AuthSession | null): Promise<CaseDetailsResponse> {
  return request<CaseDetailsResponse>(
    `/cases/${caseId}?include_snapshots=1`,
    { method: "GET" },
    { token: user?.token ?? null, base: "core_root" },
  );
}
