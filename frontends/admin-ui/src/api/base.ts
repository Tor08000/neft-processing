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

const splitBase = (base: string) => {
  if (/^https?:\/\//.test(base)) {
    const url = new URL(base);
    const basePath = url.pathname.replace(/\/+$/, "");
    return {
      origin: `${url.protocol}//${url.host}`,
      path: basePath === "/" ? "" : basePath,
    };
  }
  return { origin: "", path: base.replace(/\/+$/, "") };
};

const stripDuplicateSegment = (basePath: string, path: string, segment: string) => {
  if (!basePath.endsWith(`/${segment}`)) {
    return path;
  }
  return path.replace(new RegExp(`^${segment}(\\/|$)`), "");
};

export const joinUrl = (base: string, suffix: string): string => {
  const normalizedBase = normalizeBase(base);
  const trimmedSuffix = suffix.trim().replace(/^\/+/, "");
  if (!trimmedSuffix) {
    return normalizedBase;
  }
  const { origin, path: basePath } = splitBase(normalizedBase);
  let normalizedSuffix = trimmedSuffix;
  normalizedSuffix = stripDuplicateSegment(basePath, normalizedSuffix, "api");
  normalizedSuffix = stripDuplicateSegment(basePath, normalizedSuffix, "auth");
  const combinedPath = basePath ? `${basePath}/${normalizedSuffix}` : `/${normalizedSuffix}`;
  return origin ? `${origin}${combinedPath}` : combinedPath;
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
