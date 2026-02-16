import { request } from "./http";
import { ONBOARDING_ACCESS_TOKEN_KEY, clearOnboardingSession } from "./onboarding";

export type OnboardingDocType = "CHARTER" | "EGRUL" | "PASSPORT" | "POWER_OF_ATTORNEY" | "BANK_DETAILS" | "OTHER";
export type OnboardingDocStatus = "UPLOADED" | "VERIFIED" | "REJECTED";

export interface OnboardingDocumentItem {
  id: string;
  doc_type: OnboardingDocType;
  filename: string;
  status: OnboardingDocStatus;
  size: number;
  mime: string;
  rejection_reason?: string | null;
  created_at: string;
}

export interface ListOnboardingDocumentsResponse {
  items: OnboardingDocumentItem[];
}

const ONBOARDING_DOCS_BASE = "/client/v1/onboarding";

function onboardingToken(): string {
  const token = localStorage.getItem(ONBOARDING_ACCESS_TOKEN_KEY);
  if (!token) {
    throw new Error("Сессия заявки устарела, начните заново");
  }
  return token;
}

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

function handleAuthError(error: unknown): never {
  const maybe = error as { status?: number };
  if (maybe?.status === 401 || maybe?.status === 403) {
    clearOnboardingSession();
    throw new Error("Сессия заявки устарела, начните заново");
  }
  throw error;
}

export async function uploadOnboardingDocument(appId: string, docType: OnboardingDocType, file: File): Promise<OnboardingDocumentItem> {
  const token = onboardingToken();
  const formData = new FormData();
  formData.append("doc_type", docType);
  formData.append("file", file);

  try {
    return await request<OnboardingDocumentItem>(
      `${ONBOARDING_DOCS_BASE}/applications/${appId}/documents`,
      { method: "POST", body: formData, headers: authHeaders(token) },
      { base: "core", token },
    );
  } catch (error) {
    return handleAuthError(error);
  }
}

export async function listOnboardingDocuments(appId: string): Promise<OnboardingDocumentItem[]> {
  const token = onboardingToken();
  try {
    const res = await request<ListOnboardingDocumentsResponse>(
      `${ONBOARDING_DOCS_BASE}/applications/${appId}/documents`,
      { method: "GET", headers: authHeaders(token) },
      { base: "core", token },
    );
    return res.items;
  } catch (error) {
    return handleAuthError(error);
  }
}

export async function downloadOnboardingDocument(docId: string, filename: string): Promise<void> {
  const token = onboardingToken();
  try {
    const response = await fetch(`/api/core${ONBOARDING_DOCS_BASE}/documents/${docId}/download`, {
      method: "GET",
      headers: authHeaders(token),
    });
    if (response.status === 401 || response.status === 403) {
      clearOnboardingSession();
      throw new Error("Сессия заявки устарела, начните заново");
    }
    if (!response.ok) {
      throw new Error("Не удалось скачать документ");
    }
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    return handleAuthError(error);
  }
}


export type GeneratedDocKind = "OFFER" | "SERVICE_AGREEMENT" | "DPA" | "APP_FORM";
export type GeneratedDocStatus = "DRAFT" | "GENERATED" | "SIGNED_BY_PLATFORM" | "SIGNED_BY_CLIENT";

export interface GeneratedOnboardingDocumentItem {
  id: string;
  client_application_id?: string | null;
  doc_kind: GeneratedDocKind;
  version: number;
  filename: string;
  mime: string;
  size?: number | null;
  status: GeneratedDocStatus;
  template_id?: string | null;
  created_at: string;
}

interface GeneratedDocumentsListResponse {
  items: GeneratedOnboardingDocumentItem[];
}

export async function generateOnboardingDocuments(appId: string): Promise<GeneratedOnboardingDocumentItem[]> {
  const token = onboardingToken();
  try {
    const res = await request<GeneratedDocumentsListResponse>(
      `${ONBOARDING_DOCS_BASE}/applications/${appId}/generate-docs`,
      { method: "POST", headers: authHeaders(token) },
      { base: "core", token },
    );
    return res.items;
  } catch (error) {
    return handleAuthError(error);
  }
}

export async function listGeneratedOnboardingDocuments(appId: string): Promise<GeneratedOnboardingDocumentItem[]> {
  const token = onboardingToken();
  try {
    const res = await request<GeneratedDocumentsListResponse>(
      `${ONBOARDING_DOCS_BASE}/applications/${appId}/generated-docs`,
      { method: "GET", headers: authHeaders(token) },
      { base: "core", token },
    );
    return res.items;
  } catch (error) {
    return handleAuthError(error);
  }
}

export async function downloadGeneratedOnboardingDocument(docId: string, filename: string): Promise<void> {
  const token = onboardingToken();
  try {
    const response = await fetch(`/api/core${ONBOARDING_DOCS_BASE}/generated-docs/${docId}/download`, {
      method: "GET",
      headers: authHeaders(token),
    });
    if (response.status === 401 || response.status === 403) {
      clearOnboardingSession();
      throw new Error("Сессия заявки устарела, начните заново");
    }
    if (!response.ok) {
      throw new Error("Не удалось скачать документ");
    }
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (error) {
    return handleAuthError(error);
  }
}
