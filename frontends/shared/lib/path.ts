const isAbsoluteUrl = (value: string): boolean => /^[a-z][a-z0-9+.-]*:/.test(value) || value.startsWith("//");

const splitSuffix = (value: string) => {
  const match = value.match(/^[^?#]*/);
  const pathPart = match ? match[0] : "";
  const suffix = value.slice(pathPart.length);
  return { pathPart, suffix };
};

export const normalizeBase = (rawBase: string): string => {
  const trimmed = rawBase.trim();
  if (!trimmed) return "";
  const withLeading = trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
  const collapsed = withLeading.replace(/\/+/g, "/");
  if (collapsed === "/") return "/";
  return collapsed.endsWith("/") ? collapsed.slice(0, -1) : collapsed;
};

const normalizePath = (rawPath: string): string => {
  const trimmed = rawPath.trim();
  const { pathPart, suffix } = splitSuffix(trimmed);
  const pathRoot = pathPart ? (pathPart.startsWith("/") ? pathPart : `/${pathPart}`) : "/";
  const collapsed = pathRoot.replace(/\/+/g, "/");
  return `${collapsed}${suffix}`;
};

export const withBase = (path: string): string => {
  if (!path) return path;
  if (path.startsWith("#") || isAbsoluteUrl(path)) return path;
  const base = normalizeBase(import.meta.env.VITE_PUBLIC_BASE ?? "");
  const normalizedPath = normalizePath(path);
  if (!base || base === "/") return normalizedPath;
  if (normalizedPath === "/") return `${base}/`;
  return `${base}${normalizedPath}`.replace(/\/+/g, "/");
};
