import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { ApiError, fetchMe, HtmlResponseError, login, UnauthorizedError, ValidationError } from "../api/auth";
import { request } from "../api/http";
import type { AuthSession, LoginResponse } from "../api/types";
import { clearTokens, getAccessToken, getExpiresAt, getRefreshToken, isAccessTokenExpired, isValidJwt, saveAuthTokens } from "../lib/apiClient";

interface AuthContextValue {
  user: AuthSession | null;
  isLoading: boolean;
  error: string | null;
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

export const AuthProvider: React.FC<AuthProviderProps> = ({ children, initialSession = null }) => {
  const [user, setUser] = useState<AuthSession | null>(initialSession);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const persist = useCallback((session: AuthSession | null) => {
    if (session) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    clearTokens();
    persist(null);
  }, [persist]);

  const finalizeSession = useCallback(
    async (session: AuthSession) => {
      if (!isClientIssuer(session.token)) {
        setError("Неверный контур входа");
        logout();
        return;
      }
      const profile = await fetchMe(session.token);
      if (!isClientRolePresent(profile.roles)) {
        setError("У вас нет доступа к клиентскому кабинету");
        logout();
        return;
      }
      const normalized: AuthSession = {
        ...session,
        email: profile.email ?? session.email,
        roles: profile.roles,
        subjectType: profile.subject_type,
        clientId: profile.client_id ?? session.clientId,
      };
      setUser(normalized);
      persist(normalized);
    },
    [logout, persist],
  );

  useEffect(() => {
    const handleUnauthorized = () => {
      logout();
    };
    window.addEventListener("client-auth-logout", handleUnauthorized);
    return () => window.removeEventListener("client-auth-logout", handleUnauthorized);
  }, [logout]);

  useEffect(() => {
    if (initialSession) {
      setIsLoading(false);
      return;
    }

    const bootstrap = async () => {
      try {
        let accessToken = getAccessToken();
        const refreshToken = getRefreshToken();

        if (!isValidJwt(accessToken)) {
          logout();
          redirectToLogin();
          return;
        }

        if (isAccessTokenExpired()) {
          if (!refreshToken) {
            logout();
            redirectToLogin();
            return;
          }
          const refreshed = await refreshSession(refreshToken);
          saveAuthTokens(refreshed.accessToken, refreshed.refreshToken, refreshed.expiresIn);
          accessToken = refreshed.accessToken;
        }

        const raw = localStorage.getItem(STORAGE_KEY);
        const stored = raw ? (JSON.parse(raw) as AuthSession) : null;
        const session: AuthSession = {
          token: accessToken,
          refreshToken: getRefreshToken() ?? undefined,
          email: stored?.email ?? "",
          roles: stored?.roles ?? [],
          subjectType: stored?.subjectType ?? "client_user",
          clientId: stored?.clientId,
          timezone: stored?.timezone,
          expiresAt: getExpiresAt() ?? Date.now(),
        };

        await finalizeSession(session);
      } catch (err) {
        if (err instanceof UnauthorizedError) {
          logout();
          redirectToLogin();
        }
      } finally {
        setIsLoading(false);
      }
    };

    void bootstrap();
  }, [finalizeSession, initialSession, logout]);

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
      try {
        const session = await login({ email, password });
        saveAuthTokens(session.token, session.refreshToken, Math.max(1, Math.floor((session.expiresAt - Date.now()) / 1000)));
        await finalizeSession(session);
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
    [finalizeSession],
  );

  const activateSession = useCallback(
    async (session: AuthSession) => {
      setError(null);
      try {
        saveAuthTokens(session.token, session.refreshToken, Math.max(1, Math.floor((session.expiresAt - Date.now()) / 1000)));
        await finalizeSession(session);
      } catch (err) {
        if (err instanceof UnauthorizedError) {
          setError("Требуется повторный вход");
          return;
        }
        setError("Сервис временно недоступен");
      }
    },
    [finalizeSession],
  );

  const value = useMemo(
    () => ({
      user,
      isLoading,
      error,
      login: handleLogin,
      activateSession,
      logout,
      setTimezone,
      hasClientRole: Boolean(user?.roles && isClientRolePresent(user.roles)),
    }),
    [user, isLoading, error, handleLogin, activateSession, logout, setTimezone],
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
