const normalizePrefix = (raw: string): string => {
  const value = raw.startsWith("/") ? raw : `/${raw}`;
  return value.replace(/\/+$/, "");
};

const API_BASE = (import.meta.env.VITE_API_BASE ?? import.meta.env.VITE_API_BASE_URL ?? "/api").replace(/\/+$/, "");

const joinBase = (base: string, raw: string): string => {
  const normalized = normalizePrefix(raw);
  if (base.endsWith(normalized)) {
    return base;
  }
  if (base.endsWith("/api/auth") && normalized.startsWith("/api/auth/")) {
    return `${base}${normalized.replace(/^\/api\/auth/, "")}`;
  }
  return `${base}${normalized}`;
};

const buildBase = (legacyPrefix: string | undefined, canonicalSuffix: string): string => {
  const fallback = canonicalSuffix.startsWith("/") ? canonicalSuffix : `/${canonicalSuffix}`;
  const raw = (legacyPrefix ?? (API_BASE ? `${API_BASE}${fallback}` : fallback)).replace(/\/+$/, "");

  if (/^https?:\/\//.test(raw)) {
    return raw;
  }

  if (API_BASE) {
    return joinBase(API_BASE, raw);
  }

  return raw.startsWith("/") ? raw : `/${raw}`;
};

export const CORE_API_BASE = buildBase(import.meta.env.VITE_CORE_API_BASE, "/api/core");
export const AUTH_API_BASE = buildBase(import.meta.env.VITE_AUTH_API_BASE, "/api/auth");
export const AI_API_BASE = buildBase(import.meta.env.VITE_AI_API_BASE, "/api/ai");
export const ADMIN_BASE_URL = (import.meta.env.BASE_URL ?? "/admin/").replace(/\/+$/, "") || "/";
export const API_BASE_URL = API_BASE;
