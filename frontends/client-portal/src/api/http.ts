import { AUTH_API_BASE, CORE_API_BASE, CORE_ROOT_API_BASE } from "./base";

export { AUTH_API_BASE, CORE_API_BASE };

type ApiBase = "core" | "auth" | "core_root";

export type HttpHeaders = Record<string, string>;


const STORAGE_KEY = "neft_client_access_token";

const getStoredToken = (): string | undefined => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return undefined;
    const parsed = JSON.parse(raw) as { token?: string };
    return parsed.token;
  } catch {
    return undefined;
  }
};

const isAuthMeRequest = (base: ApiBase, path: string) => base === "auth" && path.includes("/me");
const logErrorUrl = (url: string, status: number) => {
  if (import.meta.env.DEV && status >= 400) {
    console.info("[api-error]", { final_url: url, status });
  }
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
    } catch (err) {
      return String(value);
    }
  }
  return fallback;
};

export class UnauthorizedError extends Error {
  constructor(message = "Требуется повторный вход") {
    super(message);
    this.name = "UnauthorizedError";
  }
}

export class ValidationError extends Error {
  details?: unknown;

  constructor(message = "Ошибка валидации", details?: unknown) {
    super(message);
    this.name = "ValidationError";
    this.details = details;
  }
}

export class ApiError extends Error {
  status: number;
  correlationId: string | null;
  requestId: string | null;
  code: string | null;
  detail?: unknown;
  errorCode: string | null;
  details?: unknown;

  constructor(
    message: string,
    status: number,
    correlationId: string | null,
    requestId: string | null,
    code: string | null,
    detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.correlationId = correlationId;
    this.requestId = requestId;
    this.code = code;
    this.detail = detail;
    this.errorCode = code;
    this.details = detail;
  }

  override toString(): string {
    const codePart = this.code ?? "UNKNOWN";
    const message = this.message || "";
    return `${this.name}: ${codePart} ${this.status} ${message}`.trim();
  }
}

export class HtmlResponseError extends Error {
  status: number;
  url: string;
  contentType: string;
  bodySnippet: string;
  correlationId: string | null;

  constructor(
    message: string,
    status: number,
    url: string,
    contentType: string,
    bodySnippet: string,
    correlationId: string | null,
  ) {
    super(message);
    this.name = "HtmlResponseError";
    this.status = status;
    this.url = url;
    this.contentType = contentType;
    this.bodySnippet = bodySnippet;
    this.correlationId = correlationId;
  }
}

export class LegalRequiredError extends ApiError {
  details: unknown;

  constructor(message: string, status: number, correlationId: string | null, details: unknown) {
    super(message, status, correlationId, null, null, details);
    this.name = "LegalRequiredError";
    this.details = details;
  }
}

export class TooManyForbiddenError extends ApiError {
  constructor(url: string, correlationId: string | null = null) {
    super("Слишком много повторных 403-запросов. Обновите страницу или войдите заново.", 403, correlationId, null, "too_many_forbidden", {
      url,
      local: true,
    });
    this.name = "TooManyForbiddenError";
  }
}

const RETRYABLE_STATUSES = new Set([502, 503, 504]);
const MAX_RETRIES = 2;
const BASE_RETRY_DELAY_MS = 1_000;
const FORBIDDEN_WINDOW_MS = 10_000;
const FORBIDDEN_LIMIT = 3;
const forbiddenHistory = new Map<string, number[]>();

const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

const methodUrlKey = (method: string, url: string) => `${method.toUpperCase()} ${url}`;

const cleanupForbiddenHistory = (key: string, now: number): number[] => {
  const timestamps = forbiddenHistory.get(key) ?? [];
  const filtered = timestamps.filter((stamp) => now - stamp <= FORBIDDEN_WINDOW_MS);
  forbiddenHistory.set(key, filtered);
  return filtered;
};

const checkForbiddenStorm = (key: string): boolean => {
  const now = Date.now();
  const history = cleanupForbiddenHistory(key, now);
  return history.length >= FORBIDDEN_LIMIT;
};

const registerForbidden = (key: string): void => {
  const now = Date.now();
  const history = cleanupForbiddenHistory(key, now);
  history.push(now);
  forbiddenHistory.set(key, history);
};

const shouldRetryRequest = (attempt: number, error: unknown, response?: Response): boolean => {
  if (attempt >= MAX_RETRIES) {
    return false;
  }
  if (response) {
    return RETRYABLE_STATUSES.has(response.status);
  }
  return error instanceof TypeError;
};

const fetchWithRetry = async (url: string, init: RequestInit): Promise<Response> => {
  const method = (init.method ?? "GET").toUpperCase();
  const key = methodUrlKey(method, url);
  if (checkForbiddenStorm(key)) {
    throw new TooManyForbiddenError(url);
  }

  let attempt = 0;
  while (true) {
    try {
      const response = await fetch(url, init);
      if (response.status === 403) {
        registerForbidden(key);
      }
      if (!shouldRetryRequest(attempt, null, response)) {
        return response;
      }
    } catch (error) {
      if (!shouldRetryRequest(attempt, error)) {
        throw error;
      }
    }
    const delay = BASE_RETRY_DELAY_MS * 2 ** attempt;
    await sleep(delay);
    attempt += 1;
  }
};

const buildHeaders = (token?: string): HttpHeaders => {
  const headers: HttpHeaders = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
};

const buildAuthHeaders = (token?: string): HttpHeaders => {
  const headers: HttpHeaders = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
};

type RequestOptions = {
  token?: string | null;
  base?: ApiBase;
};

export async function request<T>(
  path: string,
  init: RequestInit = {},
  tokenOrOptions?: string | null | RequestOptions,
  maybeBase?: ApiBase,
): Promise<T> {
  let token: string | null | undefined;
  let base: ApiBase = "core";
  if (tokenOrOptions && typeof tokenOrOptions === "object" && !Array.isArray(tokenOrOptions)) {
    token = tokenOrOptions.token ?? getStoredToken();
    base = tokenOrOptions.base ?? base;
  } else {
    token = (tokenOrOptions as string | null | undefined) ?? getStoredToken();
    if (typeof maybeBase === "string") {
      base = maybeBase;
    }
  }

  const headers: HttpHeaders = { ...buildHeaders(token ?? undefined), ...(init.headers as HttpHeaders | undefined) };
  const apiBase = base === "auth" ? AUTH_API_BASE : base === "core_root" ? CORE_ROOT_API_BASE : CORE_API_BASE;
  const url = `${apiBase}${path}`;
  const response = await fetchWithRetry(url, { ...init, headers });
  const correlationId = response.headers.get("x-correlation-id") ?? response.headers.get("x-request-id");
  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const isAuthLogin = base === "auth" && path.includes("/login");
  const shouldLogAuth = import.meta.env.DEV && isAuthLogin;
  let responseText: string | null = null;

  const readResponseText = async () => {
    if (responseText !== null) {
      return responseText;
    }
    responseText = await response.text().catch(() => "");
    return responseText;
  };

  if (shouldLogAuth) {
    const snippet = isJson ? "" : (await readResponseText()).slice(0, 200);
    console.info("[auth-login]", {
      url,
      status: response.status,
      contentType,
      bodySnippet: snippet || null,
    });
  }

  logErrorUrl(url, response.status);

  if (response.status === 401) {
    if (isAuthMeRequest(base, path)) {
      window.dispatchEvent(new Event("client-auth-logout"));
    }
    throw new UnauthorizedError();
  }
  if (response.status === 403) {
    window.dispatchEvent(new Event("client-auth-forbidden"));
  }
  if (response.status >= 500) {
    window.dispatchEvent(new CustomEvent("client-api-error", { detail: { status: response.status, url } }));
  }
  if (response.status === 422) {
    const details = isJson ? await response.json().catch(() => undefined) : await readResponseText();
    throw new ValidationError("Ошибка валидации", details);
  }
  if (response.status === 428) {
    const details = isJson ? await response.json().catch(() => undefined) : await readResponseText();
    window.dispatchEvent(new CustomEvent("legal-required", { detail: details }));
    throw new LegalRequiredError(
      "Legal documents must be accepted before performing this action.",
      response.status,
      correlationId,
      details,
    );
  }
  if (contentType.includes("text/html")) {
    const body = await readResponseText();
    throw new HtmlResponseError(
      "HTML response from gateway",
      response.status,
      url,
      contentType,
      body.slice(0, 200),
      correlationId,
    );
  }
  if (!response.ok) {
    const text = await readResponseText();
    let payload:
      | { error?: unknown; message?: unknown; request_id?: string; details?: unknown; detail?: unknown }
      | null = null;
    if (isJson && text) {
      try {
        payload = JSON.parse(text) as {
          error?: unknown;
          message?: unknown;
          request_id?: string;
          details?: unknown;
          detail?: unknown;
        };
      } catch (err) {
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
        ? payload?.error
        : typeof payload?.message === "string"
          ? payload?.message
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
  }

  if (response.status === 204) {
    return {} as T;
  }

  return isJson ? (response.json() as Promise<T>) : ({} as Promise<T>);
}

export interface ApiResponse<T> {
  data: T;
  correlationId: string | null;
  status: number;
}

export async function requestWithMeta<T>(
  path: string,
  init: RequestInit = {},
  tokenOrOptions?: string | null | RequestOptions,
  maybeBase?: ApiBase,
): Promise<ApiResponse<T>> {
  let token: string | null | undefined;
  let base: ApiBase = "core";
  if (tokenOrOptions && typeof tokenOrOptions === "object" && !Array.isArray(tokenOrOptions)) {
    token = tokenOrOptions.token ?? getStoredToken();
    base = tokenOrOptions.base ?? base;
  } else {
    token = (tokenOrOptions as string | null | undefined) ?? getStoredToken();
    if (typeof maybeBase === "string") {
      base = maybeBase;
    }
  }

  const headers: HttpHeaders = { ...buildHeaders(token ?? undefined), ...(init.headers as HttpHeaders | undefined) };
  const apiBase = base === "auth" ? AUTH_API_BASE : base === "core_root" ? CORE_ROOT_API_BASE : CORE_API_BASE;
  const url = `${apiBase}${path}`;
  const response = await fetchWithRetry(url, { ...init, headers });
  const correlationId = response.headers.get("x-correlation-id") ?? response.headers.get("x-request-id");
  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  let responseText: string | null = null;

  const readResponseText = async () => {
    if (responseText !== null) {
      return responseText;
    }
    responseText = await response.text().catch(() => "");
    return responseText;
  };

  logErrorUrl(url, response.status);

  if (response.status === 401) {
    if (isAuthMeRequest(base, path)) {
      window.dispatchEvent(new Event("client-auth-logout"));
    }
    throw new UnauthorizedError();
  }
  if (response.status === 403) {
    window.dispatchEvent(new Event("client-auth-forbidden"));
  }
  if (response.status >= 500) {
    window.dispatchEvent(new CustomEvent("client-api-error", { detail: { status: response.status, url } }));
  }
  if (response.status === 422) {
    const details = isJson ? await response.json().catch(() => undefined) : await readResponseText();
    throw new ValidationError("Ошибка валидации", details);
  }
  if (response.status === 428) {
    const details = isJson ? await response.json().catch(() => undefined) : await readResponseText();
    window.dispatchEvent(new CustomEvent("legal-required", { detail: details }));
    throw new LegalRequiredError(
      "Legal documents must be accepted before performing this action.",
      response.status,
      correlationId,
      details,
    );
  }
  if (contentType.includes("text/html")) {
    const body = await readResponseText();
    throw new HtmlResponseError(
      "HTML response from gateway",
      response.status,
      url,
      contentType,
      body.slice(0, 200),
      correlationId,
    );
  }
  if (!response.ok) {
    const text = await readResponseText();
    let payload:
      | { error?: unknown; message?: unknown; request_id?: string; details?: unknown; detail?: unknown }
      | null = null;
    if (isJson && text) {
      try {
        payload = JSON.parse(text) as {
          error?: unknown;
          message?: unknown;
          request_id?: string;
          details?: unknown;
          detail?: unknown;
        };
      } catch (err) {
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
        ? payload?.error
        : typeof payload?.message === "string"
          ? payload?.message
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
  }

  if (response.status === 204) {
    return { data: {} as T, correlationId, status: response.status };
  }

  const data = isJson ? ((await response.json()) as T) : ({} as T);
  return { data, correlationId, status: response.status };
}

export async function requestFormData<T>(
  path: string,
  data: FormData,
  tokenOrOptions?: string | null | RequestOptions,
  maybeBase?: ApiBase,
): Promise<T> {
  let token: string | null | undefined;
  let base: ApiBase = "core";
  if (tokenOrOptions && typeof tokenOrOptions === "object" && !Array.isArray(tokenOrOptions)) {
    token = tokenOrOptions.token ?? getStoredToken();
    base = tokenOrOptions.base ?? base;
  } else {
    token = (tokenOrOptions as string | null | undefined) ?? getStoredToken();
    if (typeof maybeBase === "string") {
      base = maybeBase;
    }
  }

  const headers: HttpHeaders = buildAuthHeaders(token ?? undefined);
  const apiBase = base === "auth" ? AUTH_API_BASE : base === "core_root" ? CORE_ROOT_API_BASE : CORE_API_BASE;
  const url = `${apiBase}${path}`;
  const response = await fetchWithRetry(url, { method: "POST", body: data, headers });
  const correlationId = response.headers.get("x-correlation-id") ?? response.headers.get("x-request-id");

  logErrorUrl(url, response.status);

  if (response.status === 401) {
    if (isAuthMeRequest(base, path)) {
      window.dispatchEvent(new Event("client-auth-logout"));
    }
    throw new UnauthorizedError();
  }
  if (response.status === 403) {
    window.dispatchEvent(new Event("client-auth-forbidden"));
  }
  if (response.status >= 500) {
    window.dispatchEvent(new CustomEvent("client-api-error", { detail: { status: response.status, url } }));
  }
  if (response.status === 422) {
    const details = await response.json().catch(() => undefined);
    throw new ValidationError("Ошибка валидации", details);
  }
  if (!response.ok) {
    const text = await response.text();
    const fallbackMessage =
      response.status === 404
        ? "Неверный маршрут запроса"
        : response.status === 502 || response.status === 503
          ? "Сервис временно недоступен"
          : `Request failed with status ${response.status}`;
    const message = toMessageString(text, fallbackMessage);
    throw new ApiError(message, response.status, correlationId, null, null);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}
