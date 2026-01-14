const normalizeBase = (raw: string): string => raw.trim().replace(/\/+$/, "");

const rawApiBase = import.meta.env.VITE_API_BASE ?? import.meta.env.VITE_API_BASE_URL ?? "";
const API_BASE = rawApiBase && rawApiBase.trim() !== "" ? rawApiBase : "";
const partnerBase = normalizeBase(import.meta.env.BASE_URL ?? "/partner/");

export const joinUrl = (base: string, path: string): string => {
  const b = normalizeBase(base);
  const p = path.replace(/^\/+/, "");
  return `${b}/${p}`;
};

const buildBase = (legacyPrefix: string | undefined, defaultSuffix: string): string => {
  if (legacyPrefix && legacyPrefix.trim() !== "") {
    return normalizeBase(legacyPrefix);
  }
  return joinUrl(API_BASE, defaultSuffix);
};

export const CORE_API_BASE = joinUrl(
  buildBase(import.meta.env.VITE_CORE_API_BASE, "api/core"),
  `${partnerBase}/api/v1`,
);
export const CORE_ROOT_API_BASE = buildBase(import.meta.env.VITE_CORE_API_BASE, "api/core").replace(/\/+$/, "");
export const AUTH_API_BASE = buildBase(import.meta.env.VITE_AUTH_API_BASE, "api/auth");
export const AI_API_BASE = joinUrl(buildBase(import.meta.env.VITE_AI_API_BASE, "api/ai"), "/api/v1");
export const PARTNER_BASE_PATH = partnerBase;
export const API_BASE_URL = API_BASE;
