import { AUTH_API_BASE, CORE_API_BASE, CORE_ROOT_API_BASE, INT_API_BASE, V1_API_BASE } from "./base";
import { isDemoPartner } from "@shared/demo/demo";

export { AUTH_API_BASE, CORE_API_BASE, INT_API_BASE, V1_API_BASE };

type ApiBase = "core" | "auth" | "core_root" | "int" | "v1";

export type HttpHeaders = Record<string, string>;

const isDebugHttpEnabled = () => Boolean(import.meta.env.DEV && import.meta.env.VITE_PARTNER_DEBUG_HTTP === "true");
const isAuthMeRequest = (base: ApiBase, path: string) => base === "auth" && path.includes("/me");
const logErrorUrl = (url: string, status: number) => {
  if (isDebugHttpEnabled() && status >= 400) {
    console.info("[api-error]", { final_url: url, status });
  }
};
const DEMO_AUTH_STORAGE_KEY = "neft_partner_access_token";
const getDemoPartnerEmail = () => {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(DEMO_AUTH_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { email?: string | null };
    return parsed.email ?? null;
  } catch {
    return null;
  }
};
const logDemoStatus = (url: string, status: number) => {
  if (status !== 403 && status !== 404) return;
  if (isDebugHttpEnabled() && isDemoPartner(getDemoPartnerEmail())) {
    console.debug("[api-demo]", { final_url: url, status });
  }
};
const warnDemoApiCall = (url: string) => {
  if (isDebugHttpEnabled() && isDemoPartner(getDemoPartnerEmail())) {
    console.warn("API call in demo is not allowed", url);
  }
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
  errorCode: string | null;
  details?: unknown;

  constructor(
    message: string,
    status: number,
    correlationId: string | null,
    requestId: string | null,
    errorCode: string | null,
    details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.correlationId = correlationId;
    this.requestId = requestId;
    this.errorCode = errorCode;
    this.details = details;
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
    token = tokenOrOptions.token ?? undefined;
    base = tokenOrOptions.base ?? base;
  } else {
    token = (tokenOrOptions as string | null | undefined) ?? undefined;
    if (typeof maybeBase === "string") {
      base = maybeBase;
    }
  }

  const headers: HttpHeaders = { ...buildHeaders(token ?? undefined), ...(init.headers as HttpHeaders | undefined) };
  const apiBase =
    base === "auth"
      ? AUTH_API_BASE
      : base === "core_root"
        ? CORE_ROOT_API_BASE
        : base === "int"
          ? INT_API_BASE
          : base === "v1"
            ? V1_API_BASE
            : CORE_API_BASE;
  const url = `${apiBase}${path}`;
  warnDemoApiCall(url);
  const response = await fetch(url, { ...init, headers });
  const correlationId = response.headers.get("x-correlation-id") ?? response.headers.get("x-request-id");
  const contentType = response.headers.get("content-type") ?? "";
  const isJson = contentType.includes("application/json");
  const isAuthLogin = base === "auth" && path.includes("/login");
  const shouldLogAuth = isDebugHttpEnabled() && isAuthLogin;
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
      window.dispatchEvent(new Event("partner-auth-logout"));
    }
    throw new UnauthorizedError();
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
    let payload: { error?: string; message?: string; detail?: string; request_id?: string; details?: unknown } | null = null;
    if (isJson && text) {
      try {
        payload = JSON.parse(text) as { error?: string; message?: string; request_id?: string; details?: unknown };
      } catch (err) {
        payload = null;
      }
    }
    const fallbackMessage =
      response.status === 404
        ? "Неверный маршрут запроса"
        : response.status === 502 || response.status === 503
          ? "Сервис временно недоступен"
          : `Request failed with status ${response.status}`;
    const partnerNotLinked = payload?.detail === "partner_not_linked";
    const message = partnerNotLinked
      ? "Партнёр не привязан. Обратитесь к администратору."
      : payload?.message ?? payload?.error ?? payload?.detail ?? (text || fallbackMessage);
    logDemoStatus(url, response.status);
    throw new ApiError(
      message,
      response.status,
      correlationId,
      payload?.request_id ?? null,
      payload?.error ?? null,
      payload?.details,
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
    token = tokenOrOptions.token ?? undefined;
    base = tokenOrOptions.base ?? base;
  } else {
    token = (tokenOrOptions as string | null | undefined) ?? undefined;
    if (typeof maybeBase === "string") {
      base = maybeBase;
    }
  }

  const headers: HttpHeaders = { ...buildHeaders(token ?? undefined), ...(init.headers as HttpHeaders | undefined) };
  const apiBase =
    base === "auth"
      ? AUTH_API_BASE
      : base === "core_root"
        ? CORE_ROOT_API_BASE
        : base === "int"
          ? INT_API_BASE
          : base === "v1"
            ? V1_API_BASE
            : CORE_API_BASE;
  const url = `${apiBase}${path}`;
  warnDemoApiCall(url);
  const response = await fetch(url, { ...init, headers });
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
      window.dispatchEvent(new Event("partner-auth-logout"));
    }
    throw new UnauthorizedError();
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
    let payload: { error?: string; message?: string; detail?: string; request_id?: string; details?: unknown } | null = null;
    if (isJson && text) {
      try {
        payload = JSON.parse(text) as { error?: string; message?: string; request_id?: string; details?: unknown };
      } catch (err) {
        payload = null;
      }
    }
    const fallbackMessage =
      response.status === 404
        ? "Неверный маршрут запроса"
        : response.status === 502 || response.status === 503
          ? "Сервис временно недоступен"
          : `Request failed with status ${response.status}`;
    const partnerNotLinked = payload?.detail === "partner_not_linked";
    const message = partnerNotLinked
      ? "Партнёр не привязан. Обратитесь к администратору."
      : payload?.message ?? payload?.error ?? payload?.detail ?? (text || fallbackMessage);
    logDemoStatus(url, response.status);
    throw new ApiError(
      message,
      response.status,
      correlationId,
      payload?.request_id ?? null,
      payload?.error ?? null,
      payload?.details,
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
    token = tokenOrOptions.token ?? undefined;
    base = tokenOrOptions.base ?? base;
  } else {
    token = (tokenOrOptions as string | null | undefined) ?? undefined;
    if (typeof maybeBase === "string") {
      base = maybeBase;
    }
  }

  const headers: HttpHeaders = buildAuthHeaders(token ?? undefined);
  const apiBase = base === "auth" ? AUTH_API_BASE : base === "core_root" ? CORE_ROOT_API_BASE : CORE_API_BASE;
  warnDemoApiCall(`${apiBase}${path}`);
  const response = await fetch(`${apiBase}${path}`, { method: "POST", body: data, headers });
  const correlationId = response.headers.get("x-correlation-id") ?? response.headers.get("x-request-id");

  logErrorUrl(`${apiBase}${path}`, response.status);

  if (response.status === 401) {
    if (isAuthMeRequest(base, path)) {
      window.dispatchEvent(new Event("partner-auth-logout"));
    }
    throw new UnauthorizedError();
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
    logDemoStatus(`${apiBase}${path}`, response.status);
    throw new ApiError(text || fallbackMessage, response.status, correlationId, null, null);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}
