import { request } from "./http";
import type { AuthSession } from "./types";
import type { ExplainActionCatalogItem, ExplainDiffResponse, ExplainV2Response } from "../types/explainV2";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

export function fetchExplainV2(
  user: AuthSession | null,
  params: Record<string, string | number | undefined>,
): Promise<ExplainV2Response> {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      search.set(key, String(value));
    }
  });
  return request<ExplainV2Response>(`/explain?${search.toString()}`, { method: "GET" }, withToken(user));
}

export function fetchExplainActions(
  user: AuthSession | null,
  params: Record<string, string | number | undefined>,
): Promise<ExplainActionCatalogItem[]> {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      search.set(key, String(value));
    }
  });
  return request<ExplainActionCatalogItem[]>(`/explain/actions?${search.toString()}`, { method: "GET" }, withToken(user));
}

export function fetchExplainDiff(
  user: AuthSession | null,
  params: {
    kind: "operation" | "invoice" | "order" | "kpi";
    id?: string;
    left_snapshot: string;
    right_snapshot: string;
    action_id?: string;
  },
): Promise<ExplainDiffResponse> {
  const search = new URLSearchParams();
  search.set("kind", params.kind);
  if (params.id) {
    search.set("id", params.id);
  }
  search.set("left_snapshot", params.left_snapshot);
  search.set("right_snapshot", params.right_snapshot);
  if (params.action_id) {
    search.set("action_id", params.action_id);
  }
  return request<ExplainDiffResponse>(`/explain/diff?${search.toString()}`, { method: "GET" }, withToken(user));
}
