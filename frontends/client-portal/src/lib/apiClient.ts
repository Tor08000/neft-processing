const ACCESS_TOKEN_KEY = "access_token";
const REFRESH_TOKEN_KEY = "refresh_token";
const EXPIRES_AT_KEY = "expires_at";
const ONBOARDING_STATE_KEY = "onboarding_state";

export function isValidJwt(token: unknown): token is string {
  return typeof token === "string" && token.trim() !== "" && token.split(".").length === 3;
}

export function getAccessToken(): string | null {
  const token = localStorage.getItem(ACCESS_TOKEN_KEY);
  return isValidJwt(token) ? token : null;
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function getExpiresAt(): number | null {
  const raw = localStorage.getItem(EXPIRES_AT_KEY);
  if (!raw) return null;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : null;
}

export function setTokens(accessToken: unknown, refreshToken: string | null | undefined, expiresAt: number): void {
  if (!isValidJwt(accessToken)) {
    clearTokens();
    return;
  }
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  if (refreshToken) {
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  } else {
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  }
  localStorage.setItem(EXPIRES_AT_KEY, String(expiresAt));
}

export function saveAuthTokens(accessToken: unknown, refreshToken: string | null | undefined, expiresInSec: number): void {
  const safeExpiresIn = Number.isFinite(expiresInSec) ? Math.max(1, expiresInSec) : 1;
  setTokens(accessToken, refreshToken, Date.now() + safeExpiresIn * 1000);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(EXPIRES_AT_KEY);
  localStorage.removeItem(ONBOARDING_STATE_KEY);
}

export function clearAuthTokens(): void {
  clearTokens();
}

export function isAccessTokenExpired(): boolean {
  const expiresAt = getExpiresAt();
  if (!expiresAt) return true;
  return Date.now() >= expiresAt;
}

export async function apiFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const token = getAccessToken();
  const headers = new Headers(options.headers ?? {});
  if (isValidJwt(token)) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  return fetch(url, { ...options, headers });
}
