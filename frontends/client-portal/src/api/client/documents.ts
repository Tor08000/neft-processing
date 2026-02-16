import { request } from "../http";
import type { AuthSession } from "../types";

export type ClientDocumentsDirection = "inbound" | "outbound";

export type ClientDocumentListItem = {
  id: string;
  direction: string;
  title: string;
  doc_type: string | null;
  status: string;
  counterparty_name: string | null;
  number: string | null;
  date: string | null;
  amount: string | null;
  currency: string | null;
  created_at: string;
  files_count: number;
};

export type ClientDocumentsListResponse = {
  items: ClientDocumentListItem[];
  total: number;
  limit: number;
  offset: number;
};

export type ListClientDocumentsParams = {
  direction?: ClientDocumentsDirection;
  status?: string;
  q?: string;
  limit?: number;
  offset?: number;
};

const withToken = (user: AuthSession | null): string | undefined => user?.token;

export function listClientDocuments(
  params: ListClientDocumentsParams,
  user: AuthSession | null,
): Promise<ClientDocumentsListResponse> {
  const query = new URLSearchParams();
  query.set("direction", params.direction ?? "inbound");
  if (params.status) query.set("status", params.status);
  if (params.q) query.set("q", params.q);
  query.set("limit", String(params.limit ?? 20));
  query.set("offset", String(params.offset ?? 0));
  query.set("sort", "created_at_desc");
  return request<ClientDocumentsListResponse>(`/client/documents?${query.toString()}`, { method: "GET" }, withToken(user));
}
