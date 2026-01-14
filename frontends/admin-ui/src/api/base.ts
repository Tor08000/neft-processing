const normalizeBase = (raw: string): string => raw.trim().replace(/\/+$/, "");

const rawApiBase = import.meta.env.VITE_API_BASE ?? import.meta.env.VITE_API_BASE_URL ?? "";
const API_BASE = rawApiBase && rawApiBase.trim() !== "" ? rawApiBase : "";

export const joinUrl = (base: string, path: string): string => {
  const b = normalizeBase(base);
  const rawPath = path.replace(/^\/+/, "");
  if (!b) {
    return rawPath ? `/${rawPath}` : "";
  }
  const isApiBase = /\/api$/.test(b);
  let p = rawPath;
  if (isApiBase && (p === "api" || p.startsWith("api/"))) {
    p = p.replace(/^api\/?/, "");
  }
  return p ? `${b}/${p}` : b;
};

const buildBase = (legacyPrefix: string | undefined, defaultSuffix: string): string => {
  if (legacyPrefix && legacyPrefix.trim() !== "") {
    return normalizeBase(legacyPrefix);
  }
  return joinUrl(API_BASE, defaultSuffix);
};

export const CORE_API_BASE = buildBase(import.meta.env.VITE_CORE_API_BASE, "api/core");
export const AUTH_API_BASE = buildBase(import.meta.env.VITE_AUTH_API_BASE, "api/auth");
export const AI_API_BASE = buildBase(import.meta.env.VITE_AI_API_BASE, "api/ai");
export const ADMIN_BASE_URL = (import.meta.env.BASE_URL ?? "/admin/").replace(/\/+$/, "") || "/";
export const API_BASE_URL = API_BASE;
