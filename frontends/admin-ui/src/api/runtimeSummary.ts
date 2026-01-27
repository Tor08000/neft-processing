import { request } from "./http";
import type { RuntimeSummary } from "../types/runtime";

export async function fetchRuntimeSummary(token: string): Promise<RuntimeSummary> {
  return request<RuntimeSummary>("/v1/admin/runtime/summary", { method: "GET" }, token);
}
