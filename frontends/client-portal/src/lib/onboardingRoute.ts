import { normalizeBase } from "@shared/lib/path";

const appBase = normalizeBase(import.meta.env.VITE_PUBLIC_BASE ?? "/client");

export const ONBOARDING_ROUTE = "/onboarding";
export const ONBOARDING_PLAN_ROUTE = "/onboarding/plan";
export const ONBOARDING_CONTRACT_ROUTE = "/onboarding/contract";

export function toBrowserPath(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  if (appBase === "/") {
    return normalizedPath;
  }
  if (normalizedPath === appBase || normalizedPath.startsWith(`${appBase}/`)) {
    return normalizedPath;
  }
  return `${appBase}${normalizedPath}`;
}

export function normalizeOnboardingPath(pathname: string): string {
  const normalized = pathname.replace(/\/+/g, "/");
  if (normalized.startsWith("/client/client/onboarding")) {
    return normalized.replace("/client/client/onboarding", "/client/onboarding");
  }
  return normalized;
}

export function toCanonicalOnboardingPath(pathname: string): string {
  const normalized = normalizeOnboardingPath(pathname);
  if (normalized === "/client/onboarding") return ONBOARDING_ROUTE;
  if (normalized === "/client/onboarding/plan") return ONBOARDING_PLAN_ROUTE;
  if (normalized === "/client/onboarding/contract") return ONBOARDING_CONTRACT_ROUTE;
  return normalized;
}
