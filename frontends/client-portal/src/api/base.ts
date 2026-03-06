const normalizeBase = (raw: string): string => raw.trim().replace(/\/+$/, "");
const normalizeApiPath = (path: string): string =>
  path
    .replace(/\/{2,}/g, "/")
    .replace(/\/api(\/api)+/g, "/api")
    .replace(/\/api\/v1\/auth(\/v1\/auth)+/g, "/api/v1/auth")
    .replace(/\/api\/auth(\/v1\/auth)+/g, "/api/v1/auth")
    .replace(/\/api\/auth(\/auth)+/g, "/api/v1/auth")
    .replace(/\/api\/v1\/auth(\/|$)/g, "/api/v1/auth$1")
    .replace(/\/api\/auth(\/|$)/g, "/api/v1/auth$1")
    .replace(/^\/auth\/v1\/auth(\/|$)/g, "/v1/auth$1")
    .replace(/^\/auth(\/|$)/g, "/v1/auth$1")
    .replace(/^auth\/v1\/auth(\/|$)/g, "v1/auth$1")
    .replace(/^auth(\/|$)/g, "v1/auth$1");

const normalizeApiBase = (raw: string): string => {
  const trimmed = normalizeBase(raw);
  if (!trimmed) {
    return "";
  }
  if (/^https?:\/\//i.test(trimmed)) {
    const url = new URL(trimmed);
    const normalizedPath = normalizeApiPath(url.pathname || "/").replace(/\/+$/, "");
    url.pathname = normalizedPath || "/";
    const normalized = url.toString();
    return normalized.endsWith("/") ? normalized.slice(0, -1) : normalized;
  }
  return normalizeApiPath(trimmed).replace(/\/+$/, "");
};

const extractPathname = (value: string): string => {
  if (/^https?:\/\//i.test(value)) {
    return new URL(value).pathname || "/";
  }
  return value;
};

const isBrowser = typeof window !== "undefined";

const DOCKER_INTERNAL_HOSTS = new Set([
  "gateway",
  "auth-host",
  "core-api",
  "core-host",
  "processing-core",
]);

const isDockerInternalHost = (host: string): boolean => {
  const normalized = host.toLowerCase();
  return DOCKER_INTERNAL_HOSTS.has(normalized) || normalized.endsWith(".docker.internal") || normalized.endsWith(".internal");
};

const getPathFromValue = (value: string): string => {
  const normalized = normalizeBase(value);
  if (!normalized) {
    return "";
  }
  if (/^https?:\/\//i.test(normalized)) {
    return normalizeApiPath(new URL(normalized).pathname || "/").replace(/\/+$/, "") || "/";
  }
  return normalizeApiPath(normalized).replace(/\/+$/, "");
};

const normalizeGatewayBase = (raw: string): string => {
  const pathOnly = getPathFromValue(raw);
  if (!pathOnly || pathOnly === "/") {
    return "/api";
  }
  if (pathOnly === "/api" || pathOnly.startsWith("/api/")) {
    return "/api";
  }
  return pathOnly;
};

const resolveServiceBase = (raw: string | undefined, defaultSuffix: string): string => {
  const value = raw?.trim();
  if (!value) {
    return joinUrl(API_BASE || "/api", defaultSuffix);
  }

  const pathOnly = getPathFromValue(value);
  if (!pathOnly || pathOnly === "/") {
    return joinUrl("/api", defaultSuffix);
  }

  if (pathOnly === "/api" || pathOnly.startsWith("/api/")) {
    return joinUrl("/api", defaultSuffix);
  }
  return joinUrl(pathOnly, defaultSuffix);
};

const resolveGatewayBase = (raw: string): string => {
  const trimmed = normalizeBase(raw);
  if (!trimmed) {
    return "";
  }

  if (!/^https?:\/\//i.test(trimmed)) {
    return normalizeGatewayBase(trimmed);
  }

  const url = new URL(trimmed);
  if (!isBrowser) {
    return normalizeApiBase(trimmed);
  }

  const host = url.hostname.toLowerCase();
  if (isDockerInternalHost(host) || host === window.location.hostname.toLowerCase()) {
    return normalizeGatewayBase(url.pathname || "/");
  }

  return normalizeGatewayBase(url.pathname || "/");
};

const rawApiBaseEnv = import.meta.env.VITE_API_BASE ?? import.meta.env.VITE_API_BASE_URL;
const defaultApiBase = "/api";
const rawApiBase = rawApiBaseEnv && rawApiBaseEnv.trim() !== "" ? rawApiBaseEnv : defaultApiBase;
const API_BASE = resolveGatewayBase(rawApiBase);
const clientBase = normalizeBase(import.meta.env.BASE_URL ?? "/client/");

export const joinUrl = (base: string, path: string): string => {
  const b = normalizeApiBase(base);
  let rawPath = normalizeApiPath(path.trim()).replace(/^\/+/, "");
  if (!b) {
    return rawPath ? `/${rawPath}` : "";
  }
  if (!rawPath) {
    return b;
  }
  const basePath = extractPathname(b).replace(/\/+$/, "");
  const baseSegments = basePath.split("/").filter(Boolean);
  let pathSegments = rawPath.split("/").filter(Boolean);
  for (let overlap = Math.min(baseSegments.length, pathSegments.length); overlap > 0; overlap -= 1) {
    const baseTail = baseSegments.slice(-overlap).join("/");
    const pathHead = pathSegments.slice(0, overlap).join("/");
    if (baseTail === pathHead) {
      pathSegments = pathSegments.slice(overlap);
      break;
    }
  }
  if (pathSegments.length === 0) {
    return b;
  }
  return `${b}/${pathSegments.join("/")}`;
};


export const isBrowserSafeApiBase = (value: string): boolean => {
  const path = getPathFromValue(value);
  return path === "/api" || path.startsWith("/api/");
};

export const CORE_API_BASE = resolveServiceBase(import.meta.env.VITE_CORE_API_BASE, "api/core");
export const CORE_ROOT_API_BASE = CORE_API_BASE.replace(/\/+$/, "");
export const AUTH_API_BASE = resolveServiceBase(import.meta.env.VITE_AUTH_API_BASE, "api/v1/auth");
export const AI_API_BASE = joinUrl(resolveServiceBase(import.meta.env.VITE_AI_API_BASE, "api/ai"), "/api/v1");
export const CLIENT_BASE_PATH = clientBase;
export const API_BASE_URL = API_BASE;
