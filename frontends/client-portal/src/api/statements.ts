import { request } from "./http";
import type { AuthSession } from "./types";
import type { Statement } from "../types/statements";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

export function fetchStatements(
  user: AuthSession | null,
  params: { from?: string; to?: string } = {},
): Promise<Statement[]> {
  const search = new URLSearchParams();
  if (params.from) search.set("from", params.from);
  if (params.to) search.set("to", params.to);
  const query = search.toString();
  const path = query ? `/statements?${query}` : "/statements";
  return request<Statement[]>(path, { method: "GET" }, withToken(user));
}
