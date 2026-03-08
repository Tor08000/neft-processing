import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ApiError, fetchMe, HtmlResponseError, login as loginApi, UnauthorizedError, ValidationError } from "../api/auth";
import { request } from "../api/http";
import { fetchClientMe } from "../api/clientPortal";
import { AUTH_API_BASE, isBrowserSafeApiBase } from "../api/base";
import type { AuthSession, LoginResponse } from "../api/types";
import { clearTokens, getAccessToken, getExpiresAt, getRefreshToken, isAccessTokenExpired, isValidJwt, saveAuthTokens } from "../lib/apiClient";
import { isDemoClient } from "@shared/demo/demo";

interface AuthContextValue {
  user: AuthSession | null;
  isLoading: boolean;
  error: string | null;
  authStatus: "loading" | "authenticated" | "unauthenticated";
  authError: "reauth_required" | null;
  login: (credentials: { email: string; password: string }) => Promise<void>;
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

const isCanonicalConnectRoute = (path: string) => path === "/connect" || path.startsWith("/connect/");

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
  const navigate = useNavigate();
  const location = useLocation();
  const [user, setUser] = useState<AuthSession | null>(initialSession);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [authStatus, setAuthStatus] = useState<"loading" | "authenticated" | "unauthenticated">("loading");
  const [authError, setAuthError] = useState<"reauth_required" | null>(null);
  const bootstrappedRef = useRef(false);
  const reauthInProgressRef = useRef(false);
  const authInProgressRef = useRef(false);
  const reauthRedirectedRef = useRef(false);

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

  const forceReauth = useCallback(() => {
    if (reauthInProgressRef.current || reauthRedirectedRef.current || authInProgressRef.current) {
      if (import.meta.env.DEV && authInProgressRef.current) {
        console.info("[AUTH] reauth event suppressed: auth flow in progress");
      }
      return;
    }
    reauthInProgressRef.current = true;
    reauthRedirectedRef.current = true;
    authInProgressRef.current = false;
    clearTokens();
    persist(null);
    setUser(null);
    setAuthError("reauth_required");
    setError("Требуется повторный вход");
    setAuthStatus("unauthenticated");
    const target = "/login?reauth=1";
    const current = `${location.pathname}${location.search}`;
    const skipped = current === target;

    if (import.meta.env.DEV) {
      console.info("[routing:attempt]", {
        source: "AuthContext.forceReauth",
        currentPath: current,
        requestedTargetPath: target,
        skipped,
        skipReason: skipped ? "already_target" : null,
      });
    }

    if (!skipped) {
      navigate(target, { replace: true });
    }
  }, [location.pathname, location.search, navigate, persist]);

  const navigateTo = useCallback(
    (path: string, source: string) => {
      const current = `${location.pathname}${location.search}`;
      const requestedTargetPath = path;
      const alreadyTarget = current === requestedTargetPath;
      const skippedCanonicalOnboarding =
        isCanonicalConnectRoute(location.pathname) && isCanonicalConnectRoute(path);
      const skipped = alreadyTarget || skippedCanonicalOnboarding;

      if (import.meta.env.DEV) {
        console.info("[routing:attempt]", {
          source,
          currentPath: current,
          requestedTargetPath,
          skipped,
          skipReason: alreadyTarget ? "already_target" : skippedCanonicalOnboarding ? "already_canonical_connect" : null,
        });
      }

      if (!skipped) {
        navigate(path, { replace: true });
      }
    },
    [location.pathname, location.search, navigate],
  );

  const routeAfterMe = useCallback(async (session: AuthSession) => {
    const isDemoClientAccount = isDemoClient(session.email ?? null);

    const navigateByPortal = (portal: Awaited<ReturnType<typeof fetchClientMe>>) => {
      if (isDemoClientAccount) {
        navigateTo("/dashboard", "AuthContext.routeAfterMe.demo");
        return;
      }
      const target = portal.access_state === "ACTIVE" ? "/dashboard" : "/connect";
      navigateTo(target, "AuthContext.routeAfterMe.portal");
    };

    try {
      const portal = await fetchClientMe(session);
      navigateByPortal(portal);
      return;
    } catch (err) {
      if (err instanceof ApiError && (err.status === 404 || err.status === 409)) {
        navigateTo(isDemoClientAccount ? "/dashboard" : "/connect", "AuthContext.routeAfterMe.portalError404or409");
        return;
      }
      if (!(err instanceof ApiError) || err.status !== 401) {
        navigateTo("/dashboard", "AuthContext.routeAfterMe.portalFallback");
        return;
      }
    }

    if (!session.refreshToken) {
      setError("Нет доступа: токен недействителен");
      logout();
      return;
    }

    try {
      const refreshed = await refreshSession(session.refreshToken);
      saveAuthTokens(refreshed.accessToken, refreshed.refreshToken, refreshed.expiresIn);
      const refreshedSession: AuthSession = {
        ...session,
        token: refreshed.accessToken,
        refreshToken: refreshed.refreshToken,
        expiresAt: Date.now() + Math.max(1, refreshed.expiresIn) * 1000,
      };
      setUser(refreshedSession);
      persist(refreshedSession);
      const portal = await fetchClientMe(refreshedSession);
      navigateByPortal(portal);
      return;
    } catch {
      setError("Нет доступа: токен недействителен");
      logout();
    }
  }, [logout, navigateTo, persist]);

  const establishSession = useCallback(
    async (tokens: SessionTokens, options?: { shouldRoute?: boolean; source?: "login" | "signup" | "bootstrap" | "refresh" }) => {
      const shouldRoute = options?.shouldRoute ?? true;
      const source = options?.source ?? "login";
      saveAuthTokens(tokens.accessToken, tokens.refreshToken, tokens.expiresInSec);
      if (import.meta.env.DEV) {
        console.info("[AUTH] session tokens persisted", {
          source,
          hasAccessToken: Boolean(tokens.accessToken),
          hasRefreshToken: Boolean(tokens.refreshToken),
          expiresInSec: tokens.expiresInSec,
        });
      }
      try {
        if (!isClientIssuer(tokens.accessToken)) {
          setError("Неверный контур входа");
          logout();
          return;
        }
        if (import.meta.env.DEV) {
          console.info("[AUTH] calling /me", { source, hasAuthorizationHeader: true });
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
        reauthInProgressRef.current = false;
        if (shouldRoute) {
          await routeAfterMe(normalized);
        }
      } catch (err) {
        if (err instanceof UnauthorizedError) {
          if (import.meta.env.DEV) {
            console.log("[AUTH] auth_me_401 -> invalid token");
          }
          logout();
          setError("Нет доступа: токен недействителен");
          return;
        }
        throw err;
      }
    },
    [logout, persist, routeAfterMe],
  );

  useEffect(() => {
    const handleUnauthorized = () => {
      forceReauth();
    };
    window.addEventListener("client-auth-logout", handleUnauthorized);
    return () => window.removeEventListener("client-auth-logout", handleUnauthorized);
  }, [forceReauth]);

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

        if (import.meta.env.DEV) {
          const tokenLen = typeof accessToken === "string" ? accessToken.length : 0;
          const tokenPrefix = typeof accessToken === "string" ? accessToken.slice(0, 10) : "";
          console.log(`[AUTH] stored_token=${tokenLen} prefix=${tokenPrefix}`);
        }

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
          await establishSession({ accessToken: refreshed.accessToken, refreshToken: refreshed.refreshToken, expiresInSec }, { shouldRoute: false, source: "refresh" });
          return;
        }

        await establishSession(
          { accessToken, refreshToken: refreshToken ?? undefined, expiresInSec },
          { shouldRoute: false, source: "bootstrap" },
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
    async (credentials: { email: string; password: string }) => {
      if (authInProgressRef.current || reauthRedirectedRef.current) {
        return;
      }
      authInProgressRef.current = true;
      setError(null);
      setAuthError(null);
      try {
        const session = await loginApi({ email: credentials.email, password: credentials.password });
        if (import.meta.env.DEV) {
          const tokenLen = session.token.length;
          const tokenPrefix = session.token.slice(0, 10);
          console.log(`[AUTH] login_token=${tokenLen} prefix=${tokenPrefix}`);
        }
        const expiresInSec = Math.max(1, Math.floor((session.expiresAt - Date.now()) / 1000));
        await establishSession({ accessToken: session.token, refreshToken: session.refreshToken, expiresInSec }, { source: "login" });
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
            if (!isBrowserSafeApiBase(AUTH_API_BASE)) {
              setError(import.meta.env.DEV ? "Неверный URL API (ошибка конфигурации)" : "Сервис временно недоступен");
            } else {
              setError("Сервис временно недоступен");
            }
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
      } finally {
        authInProgressRef.current = false;
      }
    },
    [establishSession],
  );

  const activateSession = useCallback(
    async (session: AuthSession) => {
      if (authInProgressRef.current || reauthRedirectedRef.current) {
        return;
      }
      authInProgressRef.current = true;
      setError(null);
      setAuthError(null);
      try {
        const expiresInSec = Math.max(1, Math.floor((session.expiresAt - Date.now()) / 1000));
        await establishSession({ accessToken: session.token, refreshToken: session.refreshToken, expiresInSec }, { source: "signup" });
      } catch (err) {
        if (err instanceof UnauthorizedError) {
          setAuthError("reauth_required");
          setError("Требуется повторный вход");
          return;
        }
        setError("Сервис временно недоступен");
      } finally {
        authInProgressRef.current = false;
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
