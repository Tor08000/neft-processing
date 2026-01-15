import { CORE_API_BASE, request } from "./http";
import type { AuthSession } from "./types";

const withToken = (user: AuthSession | null): string | undefined => user?.token;

export type ClientDocItem = {
  id: string;
  type: string;
  status: string;
  date: string;
  download_url: string;
};

export type ClientDocsListResponse = {
  items: ClientDocItem[];
};

export function fetchClientDocsList(user: AuthSession | null, docType?: string) {
  const query = docType ? `?type=${encodeURIComponent(docType)}` : "";
  return request<ClientDocsListResponse>(`/client/docs/list${query}`, { method: "GET" }, withToken(user));
}

export async function downloadClientDoc(documentId: string, user: AuthSession | null): Promise<void> {
  const token = withToken(user);
  const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
  const response = await fetch(`${CORE_API_BASE}/client/docs/${documentId}/download`, { headers });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  const blob = await response.blob();
  const filename = response.headers.get("Content-Disposition")?.split("filename=")[1]?.replace(/\"/g, "");
  const fallback = `${documentId}.pdf`;
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename ?? fallback;
  link.click();
  window.URL.revokeObjectURL(url);
}
