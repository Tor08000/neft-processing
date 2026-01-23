import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { ApiError, fetchMe, HtmlResponseError, login, UnauthorizedError, ValidationError } from "../api/auth";
import { fetchClientMe } from "../api/clientPortal";
import type { AuthSession } from "../api/types";

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
  /**
   * Позволяет в тестах подставить заранее авторизованную сессию без походов в API.
   */
  initialSession?: AuthSession | null;
}

const STORAGE_KEY = "neft_client_auth";
const CLIENT_TOKEN_ISSUER = import.meta.env.VITE_CLIENT_TOKEN_ISSUER ?? "neft-client";

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  const normalized = parts[1].replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  try {
    const decoded = atob(padded);
    return JSON.parse(decoded) as Record<string, unknown>;
  } catch (err) {
    console.error("Failed to decode token payload", err);
    return null;
  }
}

function isClientIssuer(token: string): boolean {
  const payload = decodeJwtPayload(token);
  return payload?.iss === CLIENT_TOKEN_ISSUER;
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
    persist(null);
  }, [persist]);

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

  useEffect(() => {
    const handleUnauthorized = () => {
      logout();
    };
    window.addEventListener("client-auth-logout", handleUnauthorized);
    return () => window.removeEventListener("client-auth-logout", handleUnauthorized);
  }, [logout]);

  const reviveSession = useCallback(
    async (stored: AuthSession) => {
      try {
        if (!isClientIssuer(stored.token)) {
          setError("Неверный контур входа");
          logout();
          return;
        }
        const profile = await fetchMe(stored.token);
        let timezone: string | null | undefined = stored.timezone;
        try {
          const clientProfile = await fetchClientMe(stored);
          timezone = clientProfile.user.timezone ?? null;
        } catch (err) {
          console.warn("Не удалось загрузить timezone клиента", err);
        }
        if (!isClientRolePresent(profile.roles)) {
          setError("Эта зона доступна только клиентам");
          logout();
          return;
        }
        const normalized: AuthSession = {
          ...stored,
          roles: profile.roles,
          email: profile.email ?? stored.email,
          subjectType: profile.subject_type,
          clientId: profile.client_id ?? stored.clientId,
          timezone,
        };
        setUser(normalized);
        persist(normalized);
      } catch (err) {
        if (err instanceof UnauthorizedError) {
          logout();
        }
      } finally {
        setIsLoading(false);
      }
    },
    [logout, persist],
  );

  useEffect(() => {
    if (initialSession) {
      setIsLoading(false);
      return;
    }
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      try {
        const stored = JSON.parse(raw) as AuthSession;
        if (stored.expiresAt > Date.now()) {
          void reviveSession(stored);
          return;
        }
      } catch (err) {
        console.error("Не удалось восстановить сессию", err);
      }
    }
    setIsLoading(false);
  }, [initialSession, reviveSession]);

  const finalizeSession = useCallback(
    async (session: AuthSession) => {
      if (!isClientIssuer(session.token)) {
        setError("Неверный контур входа");
        logout();
        return;
      }
      const profile = await fetchMe(session.token);
      let timezone: string | null | undefined = session.timezone;
      try {
        const clientProfile = await fetchClientMe(session);
        timezone = clientProfile.user.timezone ?? null;
      } catch (err) {
        console.warn("Не удалось загрузить timezone клиента", err);
      }
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
        timezone,
      };
      setUser(normalized);
      persist(normalized);
    },
    [logout, persist],
  );

  const handleLogin = useCallback(
    async (email: string, password: string) => {
      setError(null);
      try {
        const session = await login({ email, password });
        if (!isClientRolePresent(session.roles)) {
          setError("У вас нет доступа к клиентскому кабинету");
          logout();
          return;
        }
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
          console.error("Gateway returned HTML during login", {
            url: err.url,
            status: err.status,
            contentType: err.contentType,
            snippet: err.bodySnippet,
          });
          setError("Gateway returned HTML (wrong endpoint or SPA fallback)");
          return;
        }
        if (err instanceof ApiError) {
          if (err.status === 404) {
            setError(
              import.meta.env.DEV
                ? "Неверный URL API (ошибка конфигурации)"
                : "Сервис временно недоступен",
            );
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
        console.error("Ошибка авторизации", err);
        setError("Сервис временно недоступен");
      }
    },
    [finalizeSession, logout],
  );

  const activateSession = useCallback(
    async (session: AuthSession) => {
      setError(null);
      try {
        await finalizeSession(session);
      } catch (err) {
        if (err instanceof UnauthorizedError) {
          setError("Требуется повторный вход");
          return;
        }
        if (err instanceof ApiError) {
          if (err.status === 404) {
            setError(
              import.meta.env.DEV
                ? "Неверный URL API (ошибка конфигурации)"
                : "Сервис временно недоступен",
            );
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
        console.error("Ошибка авторизации", err);
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
