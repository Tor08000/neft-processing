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

export type ClientDocumentFile = {
  id: string;
  filename: string;
  mime: string;
  size: number;
  sha256: string | null;
  created_at: string;
};

export type ClientDocumentDetails = {
  id: string;
  client_id: string;
  direction: string;
  title: string;
  doc_type: string | null;
  description: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  files: ClientDocumentFile[];
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

export function createOutboundDocument(
  payload: { title: string; doc_type?: string; description?: string },
  user: AuthSession | null,
): Promise<ClientDocumentDetails> {
  return request<ClientDocumentDetails>("/client/documents", { method: "POST", body: JSON.stringify(payload) }, withToken(user));
}

export function getClientDocument(documentId: string, user: AuthSession | null): Promise<ClientDocumentDetails> {
  return request<ClientDocumentDetails>(`/client/documents/${documentId}`, { method: "GET" }, withToken(user));
}

export function uploadClientDocumentFile(documentId: string, file: File, user: AuthSession | null): Promise<ClientDocumentFile> {
  const body = new FormData();
  body.append("file", file);
  return request<ClientDocumentFile>(`/client/documents/${documentId}/upload`, { method: "POST", body }, withToken(user));
}

export async function downloadClientDocumentFile(fileId: string, user: AuthSession | null): Promise<void> {
  const token = withToken(user);
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`/api/core/client/documents/files/${fileId}/download`, { method: "GET", headers });
  if (!response.ok) {
    throw new Error(`download_failed_${response.status}`);
  }
  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") || "";
  const match = disposition.match(/filename="([^"]+)"/i);
  const filename = match?.[1] ?? "document";
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
