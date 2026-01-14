const normalizePrefix = (raw: string): string => {
  const value = raw.startsWith("/") ? raw : `/${raw}`;
  return value.replace(/\/+$/, "");
};

const API_BASE = (import.meta.env.VITE_API_BASE ?? import.meta.env.VITE_API_BASE_URL ?? "/api").replace(/\/+$/, "");
const clientBase = (import.meta.env.BASE_URL ?? "/client/").replace(/\/+$/, "");

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

const normalizeAuthBase = (base: string): string => {
  const trimmed = base.replace(/\/+$/, "");
  if (trimmed.endsWith("/v1/auth")) {
    return trimmed;
  }
  if (trimmed.endsWith("/api/v1/auth")) {
    return trimmed.replace(/\/api\/v1\/auth$/, "/v1/auth");
  }
  if (trimmed.endsWith("/api/auth")) {
    return `${trimmed}/v1/auth`;
  }
  return `${trimmed}/api/v1/auth`;
};

export const CORE_API_BASE = `${buildBase(import.meta.env.VITE_CORE_API_BASE, "/api/core")}${clientBase}/api/v1`.replace(
  /\/+$/,
  "",
);
export const CORE_ROOT_API_BASE = buildBase(import.meta.env.VITE_CORE_API_BASE, "/api/core").replace(/\/+$/, "");
export const AUTH_API_BASE = normalizeAuthBase(buildBase(import.meta.env.VITE_AUTH_API_BASE, "/api/auth")).replace(
  /\/+$/,
  "",
);
export const AI_API_BASE = `${buildBase(import.meta.env.VITE_AI_API_BASE, "/api/ai")}/api/v1`.replace(/\/+$/, "");
export const CLIENT_BASE_PATH = clientBase;
export const API_BASE_URL = API_BASE;
