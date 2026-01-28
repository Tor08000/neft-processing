const normalizeBase = (raw: string): string => raw.trim().replace(/\/+$/, "");
const normalizeApiPath = (path: string): string =>
  path
    .replace(/\/{2,}/g, "/")
    .replace(/\/api(\/api)+/g, "/api")
    .replace(/\/api\/v1\/auth(\/v1\/auth)+/g, "/api/v1/auth")
    .replace(/\/api\/auth(\/v1\/auth)+/g, "/api/v1/auth")
    .replace(/\/api\/auth(\/auth)+/g, "/api/v1/auth")
    .replace(/\/api\/v1\/auth(\/|$)/g, "/api/v1/auth$1")
    .replace(/\/api\/auth(\/|$)/g, "/api/v1/auth$1");

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

const rawApiBaseEnv = import.meta.env.VITE_API_BASE ?? import.meta.env.VITE_API_BASE_URL;
const rawApiBase = rawApiBaseEnv && rawApiBaseEnv.trim() !== "" ? rawApiBaseEnv : "/api";
const API_BASE = normalizeApiBase(rawApiBase);

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

const buildBase = (legacyPrefix: string | undefined, defaultSuffix: string): string => {
  if (legacyPrefix && legacyPrefix.trim() !== "") {
    return normalizeApiBase(legacyPrefix);
  }
  return joinUrl(API_BASE, defaultSuffix);
};

export const CORE_API_BASE = buildBase(import.meta.env.VITE_CORE_API_BASE, "api/core");
export const AUTH_API_BASE = buildBase(import.meta.env.VITE_AUTH_API_BASE, "api/v1/auth");
export const AI_API_BASE = buildBase(import.meta.env.VITE_AI_API_BASE, "api/ai");
export const ADMIN_API_BASE = import.meta.env.VITE_ADMIN_API_BASE?.trim()
  ? normalizeApiBase(import.meta.env.VITE_ADMIN_API_BASE)
  : joinUrl(CORE_API_BASE, "v1/admin");
export const ADMIN_BASE_URL = (import.meta.env.BASE_URL ?? "/admin/").replace(/\/+$/, "") || "/";
export const API_BASE_URL = API_BASE;

export const normalizeAdminPath = (path: string): string => {
  if (!path || !path.trim()) {
    return "";
  }
  let rawPath = path.trim();
  let query = "";
  let hash = "";

  const hashIndex = rawPath.indexOf("#");
  if (hashIndex >= 0) {
    hash = rawPath.slice(hashIndex);
    rawPath = rawPath.slice(0, hashIndex);
  }
  const queryIndex = rawPath.indexOf("?");
  if (queryIndex >= 0) {
    query = rawPath.slice(queryIndex);
    rawPath = rawPath.slice(0, queryIndex);
  }

  if (/^https?:\/\//i.test(rawPath)) {
    const url = new URL(rawPath);
    rawPath = url.pathname;
    query = url.search || query;
    hash = url.hash || hash;
  }

  const normalized = rawPath
    .replace(/^\/?api\/core\/v1\/admin\/?/i, "")
    .replace(/^\/?api\/v1\/admin\/?/i, "")
    .replace(/^\/?v1\/admin\/?/i, "")
    .replace(/^\/?admin\/?/i, "")
    .replace(/^\/+/, "");

  if (!normalized) {
    return "";
  }
  return `/${normalized}${query}${hash}`;
};
