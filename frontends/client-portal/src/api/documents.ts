import { CORE_API_BASE, request } from "./http";
import type { AuthSession } from "./types";
import type { DocumentAcknowledgement } from "../types/invoices";
import type { ClientDocumentList } from "../types/documents";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

export function acknowledgeDocument(
  documentType: string,
  documentId: string,
  user: AuthSession | null,
): Promise<DocumentAcknowledgement> {
  return request<DocumentAcknowledgement>(
    `/documents/${documentType}/${documentId}/ack`,
    {
      method: "POST",
    },
    withToken(user),
  );
}

export interface DocumentFilters {
  dateFrom?: string;
  dateTo?: string;
  documentType?: string;
  status?: string;
  limit?: number;
  offset?: number;
}

export function buildDocumentQuery(filters: DocumentFilters = {}): string {
  const search = new URLSearchParams();
  if (filters.dateFrom) search.set("date_from", filters.dateFrom);
  if (filters.dateTo) search.set("date_to", filters.dateTo);
  if (filters.documentType) search.set("type", filters.documentType);
  if (filters.status) search.set("status", filters.status);
  if (filters.limit) search.set("limit", String(filters.limit));
  if (filters.offset) search.set("offset", String(filters.offset));
  return search.toString();
}

export function fetchDocuments(user: AuthSession | null, filters: DocumentFilters = {}): Promise<ClientDocumentList> {
  const query = buildDocumentQuery(filters);
  const path = query ? `/documents?${query}` : "/documents";
  return request<ClientDocumentList>(path, { method: "GET" }, withToken(user));
}

const parseFilename = (header: string | null): string | null => {
  if (!header) return null;
  const match = header.match(/filename=\"?([^\";]+)\"?/i);
  return match?.[1] ?? null;
};

export async function downloadDocumentFile(
  documentId: string,
  fileType: "PDF" | "XLSX",
  user: AuthSession | null,
): Promise<void> {
  const token = withToken(user);
  const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
  const response = await fetch(`${CORE_API_BASE}/documents/${documentId}/download?file_type=${fileType}`, { headers });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  const blob = await response.blob();
  const fallback = `${documentId}.${fileType.toLowerCase()}`;
  const filename = parseFilename(response.headers.get("Content-Disposition")) ?? fallback;
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  window.URL.revokeObjectURL(url);
}

export function acknowledgeClosingDocument(
  documentId: string,
  user: AuthSession | null,
): Promise<DocumentAcknowledgement> {
  return request<DocumentAcknowledgement>(
    `/documents/${documentId}/ack`,
    {
      method: "POST",
    },
    withToken(user),
  );
}
