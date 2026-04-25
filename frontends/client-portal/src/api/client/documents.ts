import { request } from "../http";
import type { AuthSession } from "../types";

// Canonical general client documents/docflow client. Keep new generic reads/actions here;
// legacy /documents* remains only the final compatibility tail for closing-doc detail UX.

export type ClientDocumentsDirection = "inbound" | "outbound";

export type ClientDocumentStatus = "DRAFT" | "READY_TO_SEND" | "READY_TO_SIGN" | "SIGNED_CLIENT" | "CLOSED" | string;

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
  requires_action?: boolean;
  action_code?: string | null;
  ack_at?: string | null;
  edo_status?: string | null;
  period_from?: string | null;
  period_to?: string | null;
};

export type ClientDocumentFile = {
  id: string;
  filename: string;
  mime: string;
  kind?: string | null;
  size: number;
  sha256: string | null;
  created_at: string;
};

export type ClientDocumentAckDetails = {
  ack_by_user_id?: string | null;
  ack_by_email?: string | null;
  ack_ip?: string | null;
  ack_user_agent?: string | null;
  ack_method?: string | null;
  ack_at?: string | null;
};

export type ClientDocumentRiskSummary = {
  state: string;
  decided_at?: string | null;
  decision_id?: string | null;
};

export type ClientDocumentRiskExplain = Record<string, unknown>;

export type ClientDocumentDetails = {
  id: string;
  client_id: string;
  direction: string;
  title: string;
  doc_type: string | null;
  description: string | null;
  status: ClientDocumentStatus;
  created_at: string;
  updated_at: string;
  signed_by_client_at?: string | null;
  signed_by_client_user_id?: string | null;
  requires_action?: boolean;
  action_code?: string | null;
  ack_at?: string | null;
  ack_details?: ClientDocumentAckDetails | null;
  document_hash_sha256?: string | null;
  risk?: ClientDocumentRiskSummary | null;
  risk_explain?: ClientDocumentRiskExplain | null;
  files: ClientDocumentFile[];
};

export type ClientDocumentAcknowledgementResponse = {
  acknowledged: boolean;
  ack_at: string | null;
  document_type: string;
  document_object_key: string | null;
  document_hash: string | null;
};

export type ClientDocumentSignPayload = {
  consent_text_version: string;
  checkbox_confirmed: boolean;
  signer_full_name?: string;
  signer_position?: string;
};

export type ClientDocumentSignResult = {
  document_id: string;
  status: string;
  signed_by_client_at: string | null;
  signature_id: string;
  document_hash_sha256: string;
};

export type ClientDocumentSignature = {
  id: string;
  document_id: string;
  signer_user_id: string;
  signer_type: string;
  signature_method: string;
  consent_text_version: string;
  document_hash_sha256: string;
  signed_at: string;
  ip: string | null;
  user_agent: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
};

export type ClientDocumentEdoState = {
  id: string;
  document_id: string;
  client_id: string;
  provider: string | null;
  provider_mode: string;
  edo_status: string;
  edo_message_id: string | null;
  last_error_code: string | null;
  last_error_message: string | null;
  attempts_send: number;
  attempts_poll: number;
  next_poll_at: string | null;
  last_polled_at: string | null;
  last_status_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ClientDocumentTimelineEvent = {
  id: string;
  event_type: "DOCUMENT_CREATED" | "FILE_UPLOADED" | "STATUS_CHANGED" | string;
  message: string | null;
  meta: Record<string, unknown>;
  actor_type: "USER" | "SYSTEM" | string;
  actor_user_id: string | null;
  created_at: string;
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

export function acknowledgeClientDocument(
  documentId: string,
  user: AuthSession | null,
): Promise<ClientDocumentAcknowledgementResponse> {
  return request<ClientDocumentAcknowledgementResponse>(`/client/documents/${documentId}/ack`, { method: "POST" }, withToken(user));
}

export function submitClientDocument(documentId: string, user: AuthSession | null): Promise<ClientDocumentDetails> {
  return request<ClientDocumentDetails>(`/client/documents/${documentId}/submit`, { method: "POST" }, withToken(user));
}

export function getClientDocumentTimeline(documentId: string, user: AuthSession | null): Promise<ClientDocumentTimelineEvent[]> {
  return request<ClientDocumentTimelineEvent[]>(`/client/documents/${documentId}/timeline`, { method: "GET" }, withToken(user));
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

export function sendClientDocument(documentId: string, user: AuthSession | null): Promise<ClientDocumentEdoState> {
  return request<ClientDocumentEdoState>(`/client/documents/${documentId}/send`, { method: "POST" }, withToken(user));
}

export function getClientDocumentEdoState(documentId: string, user: AuthSession | null): Promise<ClientDocumentEdoState | null> {
  return request<ClientDocumentEdoState | null>(`/client/documents/${documentId}/edo`, { method: "GET" }, withToken(user));
}

export function signClientDocument(
  documentId: string,
  payload: ClientDocumentSignPayload,
  user: AuthSession | null,
): Promise<ClientDocumentSignResult> {
  return request<ClientDocumentSignResult>(`/client/documents/${documentId}/sign`, { method: "POST", body: JSON.stringify(payload) }, withToken(user));
}

export function listClientDocumentSignatures(documentId: string, user: AuthSession | null): Promise<ClientDocumentSignature[]> {
  return request<ClientDocumentSignature[]>(`/client/documents/${documentId}/signatures`, { method: "GET" }, withToken(user));
}
