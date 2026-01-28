import { request } from "./http";
import type { RuntimeSummary } from "../types/runtime";

export async function fetchRuntimeSummary(token: string): Promise<RuntimeSummary> {
  return request<RuntimeSummary>("/runtime/summary", { method: "GET" }, token);
}
