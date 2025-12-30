import { request } from "./http";
import type { AuthSession } from "./types";
import type { AccountingExportDetails, AccountingExportList } from "../types/exports";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

export function fetchExports(user: AuthSession | null): Promise<AccountingExportList> {
  return request<AccountingExportList>("/exports", { method: "GET" }, withToken(user));
}

export function fetchExportDetails(id: string, user: AuthSession | null): Promise<AccountingExportDetails> {
  return request<AccountingExportDetails>(`/exports/${id}`, { method: "GET" }, withToken(user));
}
