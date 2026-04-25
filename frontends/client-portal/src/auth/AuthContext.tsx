import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ApiError, fetchMe, HtmlResponseError, login as loginApi, UnauthorizedError, ValidationError } from "../api/auth";
import { request } from "../api/http";
import { AUTH_API_BASE, isBrowserSafeApiBase } from "../api/base";
import type { AuthSession, LoginResponse } from "../api/types";
import { clearTokens, getAccessToken, getExpiresAt, getRefreshToken, isAccessTokenExpired, isValidJwt, saveAuthTokens } from "../lib/apiClient";

interface AuthContextValue {
  user: AuthSession | null;
  isLoading: boolean;
  error: string | null;
  authStatus: "loading" | "authenticated" | "unauthenticated";
  authError: "reauth_required" | null;
  login: (credentials: { email: string; password: string }, options?: { source?: "login" | "signup" }) => Promise<void>;
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
const DEBUG_AUTH_FLOW = Boolean(import.meta.env.DEV && import.meta.env.VITE_CLIENT_DEBUG_AUTH === "true");

const isCanonicalOnboardingRoute = (path: string) => path === "/onboarding" || path.startsWith("/onboarding/");

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

function readStoredSession(): AuthSession | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<AuthSession>;
    if (!isValidJwt(parsed.token)) {
      return null;
    }
    return {
      token: parsed.token,
      refreshToken: parsed.refreshToken ?? undefined,
      email: parsed.email ?? "",
      roles: Array.isArray(parsed.roles) ? parsed.roles : [],
      subjectType: parsed.subjectType ?? "CLIENT",
      clientId: parsed.clientId ?? undefined,
      expiresAt: typeof parsed.expiresAt === "number" ? parsed.expiresAt : Date.now(),
      timezone: parsed.timezone ?? undefined,
    };
  } catch {
    return null;
  }
}

type SessionTokens = {
  accessToken: string;
  refreshToken?: string;
  expiresInSec: number;
};

type EstablishSessionOptions = {
  shouldRoute?: boolean;
  source?: "login" | "signup" | "bootstrap" | "refresh";
  onUnauthorized?: "handle" | "throw";
};

export const AuthProvider: React.FC<AuthProviderProps> = ({ children, initialSession = null }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const persistedSession = initialSession ?? readStoredSession();
  const [user, setUser] = useState<AuthSession | null>(persistedSession);
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
      if (DEBUG_AUTH_FLOW && authInProgressRef.current) {
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
    setError(null);
    setAuthStatus("unauthenticated");
    const target = "/login?reauth=1";
    const current = `${location.pathname}${location.search}`;
    const skipped = current === target;

    if (DEBUG_AUTH_FLOW) {
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
        isCanonicalOnboardingRoute(location.pathname) && isCanonicalOnboardingRoute(path) && location.pathname === path;
      const skipped = alreadyTarget || skippedCanonicalOnboarding;

      if (DEBUG_AUTH_FLOW) {
        console.info("[routing:attempt]", {
          source,
          currentPath: current,
          requestedTargetPath,
          skipped,
          skipReason: alreadyTarget ? "already_target" : skippedCanonicalOnboarding ? "already_canonical_onboarding" : null,
        });
      }

      if (!skipped) {
        navigate(path, { replace: true });
      }
    },
    [location.pathname, location.search, navigate],
  );

  const establishSession = useCallback(
    async (tokens: SessionTokens, options?: EstablishSessionOptions) => {
      const shouldRoute = options?.shouldRoute ?? true;
      const source = options?.source ?? "login";
      const onUnauthorized = options?.onUnauthorized ?? "handle";
      saveAuthTokens(tokens.accessToken, tokens.refreshToken, tokens.expiresInSec);
      if (DEBUG_AUTH_FLOW) {
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
        if (DEBUG_AUTH_FLOW) {
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
        reauthRedirectedRef.current = false;
        if (shouldRoute) {
          const postAuthRoute = source === "signup" ? "/onboarding" : "/";
          navigateTo(postAuthRoute, `AuthContext.establishSession.${source}`);
        }
      } catch (err) {
        if (err instanceof UnauthorizedError) {
          if (DEBUG_AUTH_FLOW) {
            console.log("[AUTH] auth_me_401 -> invalid token");
          }
          logout();
          if (onUnauthorized === "throw") {
            setAuthError(null);
            setError(null);
            throw err;
          }
          setAuthError("reauth_required");
          setError(null);
          return;
        }
        throw err;
      }
    },
    [logout, navigateTo, persist],
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

    if (persistedSession) {
      setAuthStatus("authenticated");
      setIsLoading(false);
      return;
    }

    const bootstrap = async () => {
      try {
        const storedSession = readStoredSession();
        let accessToken = getAccessToken() ?? storedSession?.token ?? null;
        const refreshToken = getRefreshToken() ?? storedSession?.refreshToken ?? null;
        const expiresAt = getExpiresAt() ?? storedSession?.expiresAt ?? null;

        if (DEBUG_AUTH_FLOW) {
          const tokenLen = typeof accessToken === "string" ? accessToken.length : 0;
          const tokenPrefix = typeof accessToken === "string" ? accessToken.slice(0, 10) : "";
          console.log(`[AUTH] stored_token=${tokenLen} prefix=${tokenPrefix}`);
        }

        if (!isValidJwt(accessToken)) {
          logout();
          return;
        }

        let expiresInSec = Math.max(1, Math.floor(((expiresAt ?? Date.now()) - Date.now()) / 1000));
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
  }, [establishSession, logout, persistedSession]);

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
    async (credentials: { email: string; password: string }, options?: { source?: "login" | "signup" }) => {
      if (authInProgressRef.current) {
        return;
      }
      const source = options?.source ?? "login";
      reauthInProgressRef.current = false;
      reauthRedirectedRef.current = false;
      authInProgressRef.current = true;
      setError(null);
      setAuthError(null);
      try {
        const session = await loginApi({ email: credentials.email, password: credentials.password });
        if (DEBUG_AUTH_FLOW) {
          const tokenLen = session.token.length;
          const tokenPrefix = session.token.slice(0, 10);
          console.log(`[AUTH] login_token=${tokenLen} prefix=${tokenPrefix}`);
        }
        const expiresInSec = Math.max(1, Math.floor((session.expiresAt - Date.now()) / 1000));
        await establishSession({ accessToken: session.token, refreshToken: session.refreshToken, expiresInSec }, { source });
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
        await establishSession(
          { accessToken: session.token, refreshToken: session.refreshToken, expiresInSec },
          { source: "signup", onUnauthorized: "throw" },
        );
      } catch (err) {
        if (err instanceof UnauthorizedError) {
          throw err;
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
