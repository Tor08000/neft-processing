const normalizeBase = (raw: string): string => raw.trim().replace(/\/+$/, "");
const normalizeApiPath = (path: string): string =>
  path
    .replace(/\/{2,}/g, "/")
    .replace(/\/api(\/api)+/g, "/api")
    .replace(/\/api\/auth(\/auth)+/g, "/api/auth");

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

const rawApiBase = import.meta.env.VITE_API_BASE ?? import.meta.env.VITE_API_BASE_URL ?? "";
const API_BASE = rawApiBase && rawApiBase.trim() !== "" ? rawApiBase : "";
const clientBase = normalizeBase(import.meta.env.BASE_URL ?? "/client/");

export const joinUrl = (base: string, path: string): string => {
  const b = normalizeApiBase(base);
  let rawPath = path.trim().replace(/^\/+/, "");
  if (!b) {
    return rawPath ? `/${rawPath}` : "";
  }
  if (!rawPath) {
    return b;
  }
  if (/\/api\/auth$/.test(b)) {
    if (rawPath.startsWith("api/auth/")) {
      rawPath = rawPath.slice("api/auth/".length);
    } else if (rawPath.startsWith("auth/")) {
      rawPath = rawPath.slice("auth/".length);
    }
  } else if (/\/api$/.test(b) && rawPath.startsWith("api/")) {
    rawPath = rawPath.slice("api/".length);
  }
  return `${b}/${rawPath}`;
};

const buildBase = (legacyPrefix: string | undefined, defaultSuffix: string): string => {
  if (legacyPrefix && legacyPrefix.trim() !== "") {
    return normalizeApiBase(legacyPrefix);
  }
  return joinUrl(API_BASE, defaultSuffix);
};

export const CORE_API_BASE = joinUrl(
  buildBase(import.meta.env.VITE_CORE_API_BASE, "api/core"),
  `${clientBase}/api/v1`,
);
export const CORE_ROOT_API_BASE = buildBase(import.meta.env.VITE_CORE_API_BASE, "api/core").replace(/\/+$/, "");
export const AUTH_API_BASE = buildBase(import.meta.env.VITE_AUTH_API_BASE, "api/auth");
export const AI_API_BASE = joinUrl(buildBase(import.meta.env.VITE_AI_API_BASE, "api/ai"), "/api/v1");
export const CLIENT_BASE_PATH = clientBase;
export const API_BASE_URL = API_BASE;
