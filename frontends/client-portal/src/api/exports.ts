import { request } from "./http";
import type { AuthSession } from "./types";
import type { ClientExportList } from "../types/invoices";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

export function fetchExports(user: AuthSession | null): Promise<ClientExportList> {
  return request<ClientExportList>("/exports", { method: "GET" }, withToken(user));
}
