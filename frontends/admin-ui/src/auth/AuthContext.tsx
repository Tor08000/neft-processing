import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { login as apiLogin } from "../api/auth";
import { verifyAdminAuth } from "../api/adminAuth";
import { AdminMeError, fetchAdminMe } from "../api/adminMe";
import { ApiError, ForbiddenError, HtmlResponseError, UnauthorizedError, ValidationError } from "../api/http";
import type { AuthSession, AuthUser } from "../types/auth";
import { hasAdminRole } from "./roles";

interface AuthContextValue {
  user: AuthUser | null;
  accessToken: string | null;
  roles: string[];
  isLoading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  isAdmin: boolean;
}

const STORAGE_KEY = "neft_admin_access_token";

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [roles, setRoles] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const persist = useCallback((payload: AuthSession | null) => {
    if (payload) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    setAccessToken(null);
    setRoles([]);
    persist(null);
  }, [persist]);

  const revive = useCallback(
    async (stored: AuthSession) => {
      try {
        await verifyAdminAuth(stored.accessToken);
        const adminProfile = await fetchAdminMe(stored.accessToken);
        if (!hasAdminRole(adminProfile.admin_user.roles)) {
          setError("У вас нет прав доступа к админской панели");
          logout();
          return;
        }
        const normalized: AuthUser = {
          id: adminProfile.admin_user.id,
          email: adminProfile.admin_user.email ?? stored.email ?? "",
          roles: adminProfile.admin_user.roles,
          subjectType: "admin",
        };
        setUser(normalized);
        setRoles(adminProfile.admin_user.roles);
        setAccessToken(stored.accessToken);
        persist({ ...stored, roles: adminProfile.admin_user.roles, email: normalized.email || stored.email });
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
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      try {
        const saved = JSON.parse(raw) as AuthSession;
        if (saved.expiresAt > Date.now()) {
          void revive(saved);
          return;
        }
      } catch (err) {
        console.error("Не удалось восстановить сессию", err);
      }
    }
    setIsLoading(false);
  }, [revive]);

  const handleLogin = useCallback(
    async (email: string, password: string) => {
      setError(null);
      try {
        const session = await apiLogin({ email, password });
        await verifyAdminAuth(session.accessToken);
        const adminProfile = await fetchAdminMe(session.accessToken);
        if (!hasAdminRole(adminProfile.admin_user.roles)) {
          setError("У вас нет прав доступа к админской панели");
          logout();
          return;
        }
        const normalized: AuthUser = {
          id: adminProfile.admin_user.id,
          email: adminProfile.admin_user.email ?? session.email ?? "",
          roles: adminProfile.admin_user.roles,
          subjectType: "admin",
        };
        setUser(normalized);
        setAccessToken(session.accessToken);
        setRoles(adminProfile.admin_user.roles);
        persist({ ...session, email: normalized.email || session.email, roles: adminProfile.admin_user.roles });
      } catch (err) {
        if (err instanceof UnauthorizedError) {
          setError("Неверный email или пароль");
          return;
        }
        if (err instanceof ForbiddenError) {
          setError("У вас нет прав доступа к админской панели");
          return;
        }
        if (err instanceof ValidationError) {
          setError("Проверьте email и пароль");
          return;
        }
        if (err instanceof AdminMeError) {
          if (err.status === 401) {
            setError("Требуется повторный вход");
            return;
          }
          if (err.status === 403) {
            setError("У вас нет прав доступа к админской панели");
            return;
          }
          if (err.status === 404 && import.meta.env.DEV) {
            setError("API маршрут админ-портала не настроен");
            return;
          }
          if (err.status === 404) {
            setError("Маршрут портала недоступен");
            return;
          }
          if (err.status === 502 || err.status === 503 || err.status === 504) {
            setError("Сервис временно недоступен");
            return;
          }
          if (err.status >= 500) {
            setError("Техническая ошибка");
            return;
          }
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
          if (err.status === 404 && import.meta.env.DEV) {
            setError("API маршрут админ-портала не настроен");
            return;
          }
          if (err.status === 404) {
            setError("Маршрут портала недоступен");
            return;
          }
          if (err.status === 502 || err.status === 503 || err.status === 504) {
            setError("Сервис временно недоступен");
            return;
          }
          if (err.status >= 500) {
            setError("Техническая ошибка");
            return;
          }
        }
        if (err instanceof TypeError) {
          setError("Сервис временно недоступен");
          return;
        }
        console.error("Ошибка авторизации", err);
        setError("Техническая ошибка");
      }
    },
    [logout, persist],
  );

  const value = useMemo(
    () => ({
      user,
      accessToken,
      roles,
      isLoading,
      error,
      login: handleLogin,
      logout,
      isAdmin: hasAdminRole(roles),
    }),
    [user, accessToken, roles, isLoading, error, handleLogin, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
