const normalizePrefix = (raw: string): string => {
  const value = raw.startsWith("/") ? raw : `/${raw}`;
  return value.replace(/\/+$/, "");
};

const API_BASE = (import.meta.env.VITE_API_BASE ?? import.meta.env.VITE_API_BASE_URL ?? "http://gateway").replace(
  /\/+$/,
  "",
);
const partnerBase = (import.meta.env.BASE_URL ?? "/partner/").replace(/\/+$/, "");

const buildBase = (legacyPrefix: string | undefined, canonicalSuffix: string): string => {
  const fallback = canonicalSuffix.startsWith("/") ? canonicalSuffix : `/${canonicalSuffix}`;
  const raw = (legacyPrefix ?? (API_BASE ? `${API_BASE}${fallback}` : fallback)).replace(/\/+$/, "");

  if (/^https?:\/\//.test(raw)) {
    return raw;
  }

  if (API_BASE) {
    const normalized = normalizePrefix(raw);
    return `${API_BASE}${normalized}`;
  }

  return raw.startsWith("/") ? raw : `/${raw}`;
};

export const CORE_API_BASE =
  `${buildBase(import.meta.env.VITE_CORE_API_BASE, "/api/core")}${partnerBase}/api/v1`.replace(/\/+$/, "");
export const AUTH_API_BASE = `${buildBase(import.meta.env.VITE_AUTH_API_BASE, "/api/auth")}/api/v1/auth`.replace(
  /\/+$/,
  "",
);
export const AI_API_BASE = `${buildBase(import.meta.env.VITE_AI_API_BASE, "/api/ai")}/api/v1`.replace(/\/+$/, "");
export const PARTNER_BASE_PATH = partnerBase;
export const API_BASE_URL = API_BASE;
