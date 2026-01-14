const normalizeBase = (raw: string): string => {
  const trimmed = raw.trim();
  if (/^https?:\/\//.test(trimmed)) {
    return trimmed.replace(/\/+$/, "");
  }
  const withLeading = trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
  return withLeading.replace(/\/+$/, "");
};

const rawApiBase = import.meta.env.VITE_API_BASE ?? import.meta.env.VITE_API_BASE_URL ?? "/api";
const API_BASE = normalizeBase(rawApiBase && rawApiBase.trim() !== "" ? rawApiBase : "/api");
const clientBase = normalizeBase(import.meta.env.BASE_URL ?? "/client/");

const joinPath = (base: string, suffix: string): string => {
  const trimmedSuffix = suffix.replace(/^\/+/, "");
  if (!trimmedSuffix) {
    return base;
  }
  return `${base}/${trimmedSuffix}`;
};

const buildBase = (legacyPrefix: string | undefined, defaultSuffix: string): string => {
  if (legacyPrefix && legacyPrefix.trim() !== "") {
    return normalizeBase(legacyPrefix);
  }
  return joinPath(API_BASE, defaultSuffix);
};

export const CORE_API_BASE = `${buildBase(import.meta.env.VITE_CORE_API_BASE, "core")}${clientBase}/api/v1`.replace(
  /\/+$/,
  "",
);
export const CORE_ROOT_API_BASE = buildBase(import.meta.env.VITE_CORE_API_BASE, "core").replace(/\/+$/, "");
export const AUTH_API_BASE = normalizeBase(import.meta.env.VITE_AUTH_API_BASE ?? "/api/auth");
export const AI_API_BASE = `${buildBase(import.meta.env.VITE_AI_API_BASE, "ai")}/api/v1`.replace(/\/+$/, "");
export const CLIENT_BASE_PATH = clientBase;
export const API_BASE_URL = API_BASE;
