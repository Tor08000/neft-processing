import { ADMIN_API_BASE, AUTH_API_BASE, normalizeAdminPath } from "./base";

type ApiBase = "core" | "auth";

export type HttpHeaders = Record<string, string>;
const logErrorUrl = (url: string, status: number) => {
  if (import.meta.env.DEV && status >= 400) {
    console.info("[api-error]", { final_url: url, status });
  }
};

export class UnauthorizedError extends Error {
  constructor(message = "Необходим повторный вход") {
    super(message);
    this.name = "UnauthorizedError";
  }
}

export class ForbiddenError extends Error {
  constructor(message = "Недостаточно прав") {
    super(message);
    this.name = "ForbiddenError";
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

export class LegalRequiredError extends Error {
  status: number;
  details: unknown;

  constructor(message: string, status: number, details: unknown) {
    super(message);
    this.name = "LegalRequiredError";
    this.status = status;
    this.details = details;
  }
}

export class ApiError extends Error {
  status: number;
  requestId: string | null;
  correlationId: string | null;
  errorCode: string | null;
  details?: unknown;

  constructor(
    message: string,
    status: number,
    requestId: string | null,
    correlationId: string | null,
    errorCode: string | null,
    details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.requestId = requestId;
    this.correlationId = correlationId;
    this.errorCode = errorCode;
    this.details = details;
  }
}

export class HtmlResponseError extends Error {
  status: number;
  url: string;
  contentType: string;
  bodySnippet: string;

  constructor(message: string, status: number, url: string, contentType: string, bodySnippet: string) {
    super(message);
    this.name = "HtmlResponseError";
    this.status = status;
    this.url = url;
    this.contentType = contentType;
    this.bodySnippet = bodySnippet;
  }
}

const buildHeaders = (token?: string | null): HttpHeaders => {
  const headers: HttpHeaders = {
    "Content-Type": "application/json",
  };

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

  const headers: HttpHeaders = {
    ...buildHeaders(token),
    ...(init.headers as HttpHeaders | undefined),
  };

  const apiBase = base === "auth" ? AUTH_API_BASE : ADMIN_API_BASE;
  const resolvedPath = base === "auth" ? path : normalizeAdminPath(path);
  const url = `${apiBase}${resolvedPath}`;
  const response = await fetch(url, { ...init, headers });
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
    throw new UnauthorizedError();
  }
  if (response.status === 403) {
    throw new ForbiddenError();
  }
  if (response.status === 422) {
    const details = isJson ? await response.json().catch(() => undefined) : await readResponseText();
    throw new ValidationError("Ошибка валидации", details);
  }
  if (response.status === 428) {
    const details = isJson ? await response.json().catch(() => undefined) : await readResponseText();
    window.dispatchEvent(new CustomEvent("legal-required", { detail: details }));
    throw new LegalRequiredError("Legal documents must be accepted before performing this action.", 428, details);
  }
  if (contentType.includes("text/html")) {
    const body = await readResponseText();
    throw new HtmlResponseError("HTML response from gateway", response.status, url, contentType, body.slice(0, 200));
  }
  if (!response.ok) {
    const text = await readResponseText();
    let payload: { error?: string; message?: string; request_id?: string; details?: unknown } | null = null;
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
    const message = payload?.message ?? payload?.error ?? (text || fallbackMessage);
    throw new ApiError(
      message,
      response.status,
      payload?.request_id ?? null,
      correlationId,
      payload?.error ?? null,
      payload?.details,
    );
  }

  return isJson ? (response.json() as Promise<T>) : ({} as Promise<T>);
}
