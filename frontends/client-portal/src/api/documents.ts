import { API_BASE_URL, joinUrl } from "./base";
import { ApiError, HtmlResponseError, LegalRequiredError, UnauthorizedError, ValidationError } from "./http";
import type { AuthSession } from "./types";
import type { DocumentAcknowledgement } from "../types/invoices";
import type { ClientDocumentDetails, ClientDocumentList } from "../types/documents";

const withToken = (user: AuthSession | null): string | undefined => user?.token;
// Legacy /documents* compatibility client. Keep for the final closing-doc detail tail;
// canonical general docflow lives under /client/documents*.

const LEGACY_DOCUMENTS_API_BASE = joinUrl(API_BASE_URL, "/api/v1/client");

type ErrorPayload = {
  error?: unknown;
  message?: unknown;
  request_id?: string;
  details?: unknown;
  detail?: unknown;
};

const toMessageString = (value: unknown, fallback: string): string => {
  if (typeof value === "string" && value.trim() !== "") {
    return value;
  }
  if (value != null && typeof value !== "string") {
    try {
      const serialized = JSON.stringify(value);
      if (serialized && serialized !== "{}") {
        return serialized;
      }
    } catch {
      return String(value);
    }
  }
  return fallback;
};

const isLikelyJsonPayload = (text: string): boolean => {
  const trimmed = text.trim();
  return trimmed.startsWith("{") || trimmed.startsWith("[");
};

const readLegacyResponseText = async (response: Response): Promise<string> => response.text().catch(() => "");

const parseLegacySuccess = <T>(text: string, isJson: boolean): T => {
  if (!text.trim()) {
    return {} as T;
  }
  if (!isJson && !isLikelyJsonPayload(text)) {
    return {} as T;
  }
  return JSON.parse(text) as T;
};

const throwLegacyResponseError = async (response: Response, url: string): Promise<never> => {
  const correlationId = response.headers.get("x-correlation-id") ?? response.headers.get("x-request-id");
  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");

  if (response.status === 401) {
    throw new UnauthorizedError();
  }
  if (response.status === 422) {
    const details = isJson ? await response.json().catch(() => undefined) : await readLegacyResponseText(response);
    throw new ValidationError("Ошибка валидации", details);
  }
  if (response.status === 428) {
    const details = isJson ? await response.json().catch(() => undefined) : await readLegacyResponseText(response);
    throw new LegalRequiredError(
      "Legal documents must be accepted before performing this action.",
      response.status,
      correlationId,
      details,
    );
  }
  if (contentType.includes("text/html")) {
    const body = await readLegacyResponseText(response);
    throw new HtmlResponseError(
      "HTML response from gateway",
      response.status,
      url,
      contentType,
      body.slice(0, 200),
      correlationId,
    );
  }

  const text = await readLegacyResponseText(response);
  let payload: ErrorPayload | null = null;
  if ((isJson || isLikelyJsonPayload(text)) && text) {
    try {
      payload = JSON.parse(text) as ErrorPayload;
    } catch {
      payload = null;
    }
  }

  const rawMessage = payload?.message ?? payload?.error ?? text;
  const fallbackMessage =
    response.status === 404
      ? "Неверный маршрут запроса"
      : response.status === 502 || response.status === 503
        ? "Сервис временно недоступен"
        : `Request failed with status ${response.status}`;
  const message = toMessageString(rawMessage, fallbackMessage);
  const code =
    typeof payload?.error === "string"
      ? payload.error
      : typeof payload?.message === "string"
        ? payload.message
        : null;
  const detail = payload?.detail ?? payload?.details;

  throw new ApiError(
    message,
    response.status,
    correlationId,
    payload?.request_id ?? null,
    code,
    detail,
  );
};

async function legacyDocumentsRequest<T>(
  path: string,
  init: RequestInit = {},
  user: AuthSession | null = null,
): Promise<T> {
  const token = withToken(user);
  const headers: HeadersInit = {
    ...(init.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(init.headers as HeadersInit | undefined),
  };
  const url = `${LEGACY_DOCUMENTS_API_BASE}${path}`;
  const response = await fetch(url, { ...init, headers });

  if (!response.ok) {
    return throwLegacyResponseError(response, url);
  }

  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const text = await readLegacyResponseText(response);
  return parseLegacySuccess<T>(text, isJson);
}

export interface DocumentFilters {
  dateFrom?: string;
  dateTo?: string;
  documentType?: string;
  status?: string;
  acknowledged?: boolean;
  limit?: number;
  offset?: number;
}

export function buildDocumentQuery(filters: DocumentFilters = {}): string {
  const search = new URLSearchParams();
  if (filters.dateFrom) search.set("date_from", filters.dateFrom);
  if (filters.dateTo) search.set("date_to", filters.dateTo);
  if (filters.documentType) search.set("type", filters.documentType);
  if (filters.status) search.set("status", filters.status);
  if (filters.acknowledged !== undefined) search.set("acknowledged", String(filters.acknowledged));
  if (filters.limit) search.set("limit", String(filters.limit));
  if (filters.offset) search.set("offset", String(filters.offset));
  return search.toString();
}

export function fetchDocuments(user: AuthSession | null, filters: DocumentFilters = {}): Promise<ClientDocumentList> {
  const query = buildDocumentQuery(filters);
  const path = query ? `/documents?${query}` : "/documents";
  return legacyDocumentsRequest<ClientDocumentList>(path, { method: "GET" }, user);
}

export function fetchDocumentDetails(documentId: string, user: AuthSession | null): Promise<ClientDocumentDetails> {
  return legacyDocumentsRequest<ClientDocumentDetails>(`/documents/${documentId}`, { method: "GET" }, user);
}

const parseFilename = (header: string | null): string | null => {
  if (!header) return null;
  const match = header.match(/filename="?([^";]+)"?/i);
  return match?.[1] ?? null;
};

export async function downloadDocumentFile(
  documentId: string,
  fileType: "PDF" | "XLSX",
  user: AuthSession | null,
): Promise<void> {
  const token = withToken(user);
  const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
  const url = `${LEGACY_DOCUMENTS_API_BASE}/documents/${documentId}/download?file_type=${fileType}`;
  const response = await fetch(url, { headers });
  if (!response.ok) {
    return throwLegacyResponseError(response, url);
  }
  const blob = await response.blob();
  const fallback = `${documentId}.${fileType.toLowerCase()}`;
  const filename = parseFilename(response.headers.get("Content-Disposition")) ?? fallback;
  const objectUrl = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  link.click();
  window.URL.revokeObjectURL(objectUrl);
}

export function acknowledgeClosingDocument(
  documentId: string,
  user: AuthSession | null,
): Promise<DocumentAcknowledgement> {
  return legacyDocumentsRequest<DocumentAcknowledgement>(
    `/documents/${documentId}/ack`,
    {
      method: "POST",
    },
    user,
  );
}
