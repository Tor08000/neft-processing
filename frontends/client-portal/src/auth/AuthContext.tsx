import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, fetchMe, HtmlResponseError, login as loginApi, UnauthorizedError, ValidationError } from "../api/auth";
import { request } from "../api/http";
import { fetchClientMe } from "../api/clientPortal";
import type { AuthSession, LoginResponse } from "../api/types";
import { AccessState, resolveAccessState } from "../access/accessState";
import { clearTokens, getAccessToken, getExpiresAt, getRefreshToken, isAccessTokenExpired, isValidJwt, saveAuthTokens } from "../lib/apiClient";

interface AuthContextValue {
  user: AuthSession | null;
  isLoading: boolean;
  error: string | null;
  authStatus: "loading" | "authenticated" | "unauthenticated";
  authError: "reauth_required" | null;
  login: (email: string, password: string) => Promise<void>;
  activateSession: (session: AuthSession) => Promise<void>;
  logout: () => void;
  setTimezone: (timezone: string | null) => void;
  hasClientRole: boolean;
}

interface AuthProviderProps {
  children: React.ReactNode;
  initialSession?: AuthSession | null;
}

const STORAGE_KEY = "neft_client_access_token";
const CLIENT_TOKEN_ISSUER = import.meta.env.VITE_CLIENT_TOKEN_ISSUER ?? "neft-auth";

const redirectToLogin = () => {
  if (typeof window !== "undefined") {
    window.location.replace("/client/login");
  }
};

const navigateTo = (path: string) => {
  if (typeof window !== "undefined") {
    window.location.replace(path);
  }
};

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  const normalized = parts[1].replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  try {
    const decoded = atob(padded);
    return JSON.parse(decoded) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function isClientIssuer(token: string): boolean {
  const payload = decodeJwtPayload(token);
  return payload?.iss === CLIENT_TOKEN_ISSUER;
}

async function refreshSession(refreshToken: string): Promise<{ accessToken: string; refreshToken: string; expiresIn: number }> {
  const body = await request<LoginResponse>(
    "/refresh",
    { method: "POST", body: JSON.stringify({ refresh_token: refreshToken }) },
    { base: "auth", token: null },
  );
  if (!body.access_token || !body.refresh_token || !body.expires_in) {
    throw new UnauthorizedError();
  }
  return { accessToken: body.access_token, refreshToken: body.refresh_token, expiresIn: body.expires_in };
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function isClientRolePresent(roles: string[]): boolean {
  return roles.some((role) => role.startsWith("CLIENT_"));
}

type SessionTokens = {
  accessToken: string;
  refreshToken?: string;
  expiresInSec: number;
};

export const AuthProvider: React.FC<AuthProviderProps> = ({ children, initialSession = null }) => {
  const [user, setUser] = useState<AuthSession | null>(initialSession);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [authStatus, setAuthStatus] = useState<"loading" | "authenticated" | "unauthenticated">("loading");
  const [authError, setAuthError] = useState<"reauth_required" | null>(null);
  const bootstrappedRef = useRef(false);

  const persist = useCallback((session: AuthSession | null) => {
    if (session) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    setAuthStatus("unauthenticated");
    clearTokens();
    persist(null);
  }, [persist]);

  const routeAfterMe = useCallback(async (session: AuthSession) => {
    if (!session) {
      redirectToLogin();
      return;
    }
    try {
      const portal = await fetchClientMe(session);
      const decision = resolveAccessState({ client: portal });
      const needsOnboarding = [AccessState.NEEDS_ONBOARDING, AccessState.NEEDS_PLAN, AccessState.NEEDS_CONTRACT].includes(decision.state);
      navigateTo(needsOnboarding ? "/client/onboarding" : "/client/dashboard");
      return;
    } catch {
      navigateTo("/client/dashboard");
    }
  }, []);

  const establishSession = useCallback(
    async (tokens: SessionTokens, options?: { shouldRoute?: boolean }) => {
      const shouldRoute = options?.shouldRoute ?? true;
      saveAuthTokens(tokens.accessToken, tokens.refreshToken, tokens.expiresInSec);
      try {
        if (!isClientIssuer(tokens.accessToken)) {
          setError("Неверный контур входа");
          logout();
          return;
        }
        const profile = await fetchMe(tokens.accessToken);
        if (!isClientRolePresent(profile.roles)) {
          setError("У вас нет доступа к клиентскому кабинету");
          logout();
          return;
        }
        const normalized: AuthSession = {
          token: tokens.accessToken,
          refreshToken: tokens.refreshToken,
          email: profile.email ?? "",
          roles: profile.roles,
          subjectType: profile.subject_type,
          clientId: profile.client_id ?? undefined,
          expiresAt: Date.now() + Math.max(1, tokens.expiresInSec) * 1000,
        };
        setUser(normalized);
        persist(normalized);
        setAuthError(null);
        setAuthStatus("authenticated");
        if (shouldRoute) {
          await routeAfterMe(normalized);
        }
      } catch (err) {
        if (err instanceof UnauthorizedError) {
          clearTokens();
          persist(null);
          setUser(null);
          setAuthError("reauth_required");
          setError("Требуется повторный вход");
          setAuthStatus("unauthenticated");
          redirectToLogin();
          return;
        }
        throw err;
      }
    },
    [logout, persist, routeAfterMe],
  );

  useEffect(() => {
    const handleUnauthorized = () => {
      clearTokens();
      persist(null);
      setUser(null);
      setAuthError("reauth_required");
      setError("Требуется повторный вход");
      setAuthStatus("unauthenticated");
      redirectToLogin();
    };
    window.addEventListener("client-auth-logout", handleUnauthorized);
    return () => window.removeEventListener("client-auth-logout", handleUnauthorized);
  }, [persist]);

  useEffect(() => {
    if (bootstrappedRef.current) {
      return;
    }
    bootstrappedRef.current = true;

    if (initialSession) {
      setAuthStatus("authenticated");
      setIsLoading(false);
      return;
    }

    const bootstrap = async () => {
      try {
        let accessToken = getAccessToken();
        const refreshToken = getRefreshToken();

        if (!isValidJwt(accessToken)) {
          logout();
          return;
        }

        let expiresInSec = Math.max(1, Math.floor(((getExpiresAt() ?? Date.now()) - Date.now()) / 1000));
        if (isAccessTokenExpired()) {
          if (!refreshToken) {
            logout();
            return;
          }
          const refreshed = await refreshSession(refreshToken);
          accessToken = refreshed.accessToken;
          expiresInSec = refreshed.expiresIn;
          await establishSession({ accessToken: refreshed.accessToken, refreshToken: refreshed.refreshToken, expiresInSec }, { shouldRoute: false });
          return;
        }

        await establishSession(
          { accessToken, refreshToken: refreshToken ?? undefined, expiresInSec },
          { shouldRoute: false },
        );
      } catch {
        logout();
      } finally {
        setIsLoading(false);
      }
    };

    void bootstrap();
  }, [establishSession, initialSession, logout]);

  const setTimezone = useCallback(
    (timezone: string | null) => {
      setUser((prev) => {
        if (!prev) return prev;
        const next = { ...prev, timezone };
        persist(next);
        return next;
      });
    },
    [persist],
  );

  const handleLogin = useCallback(
    async (email: string, password: string) => {
      setError(null);
      setAuthError(null);
      try {
        const session = await loginApi({ email, password });
        const expiresInSec = Math.max(1, Math.floor((session.expiresAt - Date.now()) / 1000));
        await establishSession({ accessToken: session.token, refreshToken: session.refreshToken, expiresInSec });
      } catch (err) {
        if (err instanceof UnauthorizedError) {
          setError("Неверный логин/пароль");
          return;
        }
        if (err instanceof ValidationError) {
          setError("Проверьте email и пароль");
          return;
        }
        if (err instanceof HtmlResponseError) {
          setError("Gateway returned HTML (wrong endpoint or SPA fallback)");
          return;
        }
        if (err instanceof ApiError) {
          if (err.status === 404) {
            setError(import.meta.env.DEV ? "Неверный URL API (ошибка конфигурации)" : "Сервис временно недоступен");
            return;
          }
          if (err.status >= 500) {
            setError("Сервис временно недоступен");
            return;
          }
        }
        if (err instanceof TypeError) {
          setError("Нет соединения");
          return;
        }
        setError("Сервис временно недоступен");
      }
    },
    [establishSession],
  );

  const activateSession = useCallback(
    async (session: AuthSession) => {
      setError(null);
      setAuthError(null);
      try {
        const expiresInSec = Math.max(1, Math.floor((session.expiresAt - Date.now()) / 1000));
        await establishSession({ accessToken: session.token, refreshToken: session.refreshToken, expiresInSec });
      } catch (err) {
        if (err instanceof UnauthorizedError) {
          setAuthError("reauth_required");
          setError("Требуется повторный вход");
          return;
        }
        setError("Сервис временно недоступен");
      }
    },
    [establishSession],
  );

  const value = useMemo(
    () => ({
      user,
      isLoading,
      error,
      authStatus,
      authError,
      login: handleLogin,
      activateSession,
      logout,
      setTimezone,
      hasClientRole: Boolean(user?.roles && isClientRolePresent(user.roles)),
    }),
    [user, isLoading, error, authStatus, authError, handleLogin, activateSession, logout, setTimezone],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return ctx;
}
