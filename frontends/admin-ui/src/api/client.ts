import { ADMIN_API_BASE, ADMIN_BASE_URL, joinUrl, normalizeAdminPath } from "./base";

export const TOKEN_STORAGE_KEY = "neft_admin_auth";

type StoredSession = {
  accessToken?: string;
  token?: string;
};

export class UnauthorizedError extends Error {
  constructor(message = "Unauthorized") {
    super(message);
    this.name = "UnauthorizedError";
  }
}

function normalizeBasePath(rawBase: string): string {
  const withLeading = rawBase.startsWith("/") ? rawBase : `/${rawBase}`;
  const normalized = withLeading.endsWith("/") ? withLeading : `${withLeading}/`;
  return normalized.replace(/\/+/g, "/");
}

const BASE_PATH = normalizeBasePath(ADMIN_BASE_URL);

function redirectToLogin() {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  const target = `${BASE_PATH}login`;
  if (window.location.pathname !== target) {
    window.location.replace(target);
  }
}

function buildUrl(path: string, params?: Record<string, unknown>): string {
  const fallbackBase = typeof window !== "undefined" ? window.location.origin : "http://localhost";
  const trimmedPath = path.trim();
  const isAbsoluteApiPath = /^https?:\/\//i.test(trimmedPath) || trimmedPath.startsWith("/api/");
  const base = ADMIN_API_BASE || fallbackBase;
  const normalizedPath = normalizeAdminPath(trimmedPath);
  const joined = normalizedPath ? joinUrl(base, normalizedPath) : base;
  const url = isAbsoluteApiPath ? new URL(trimmedPath, fallbackBase) : new URL(joined, fallbackBase);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.append(key, String(value));
      }
    });
  }
  return url.toString();
}

export function getStoredToken(): string | null {
  const raw = localStorage.getItem(TOKEN_STORAGE_KEY);
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw) as StoredSession;
    return parsed.accessToken ?? parsed.token ?? null;
  } catch (error) {
    return raw;
  }
}

function authHeaders(): Record<string, string> {
  const token = getStoredToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

class ApiClient {
  fetcher = async <T>(path: string, init?: RequestInit): Promise<T> => {
    const res = await fetch(path, init);
    if (res.status === 401) {
      redirectToLogin();
      throw new UnauthorizedError();
    }
    if (!res.ok) {
      let detail: unknown;
      try {
        detail = await res.json();
      } catch {
        detail = await res.text();
      }
      const message = typeof detail === "string" ? detail : JSON.stringify(detail);
      throw new Error(`HTTP ${res.status}: ${message}`);
    }
    if (res.status === 204) {
      return undefined as T;
    }
    return (await res.json()) as T;
  };

  async get<T>(path: string, params?: Record<string, unknown>): Promise<T> {
    const url = buildUrl(path, params);
    return this.fetcher<T>(url, {
      method: "GET",
      headers: { Accept: "application/json", ...authHeaders() },
    });
  }

  async post<T>(path: string, body?: unknown): Promise<T> {
    const url = buildUrl(path);
    return this.fetcher<T>(url, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  async put<T>(path: string, body?: unknown): Promise<T> {
    const url = buildUrl(path);
    return this.fetcher<T>(url, {
      method: "PUT",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  async patch<T>(path: string, body?: unknown): Promise<T> {
    const url = buildUrl(path);
    return this.fetcher<T>(url, {
      method: "PATCH",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...authHeaders(),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  }
}

export const apiClient = new ApiClient();
export const apiGet = apiClient.get.bind(apiClient);
export const apiPost = apiClient.post.bind(apiClient);
export const apiPut = apiClient.put.bind(apiClient);
export const apiPatch = apiClient.patch.bind(apiClient);
export const apiFetcher = apiClient.fetcher;
