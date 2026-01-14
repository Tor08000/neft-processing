import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { ApiError, fetchMe, HtmlResponseError, login, UnauthorizedError, ValidationError } from "../api/auth";
import type { AuthSession } from "../api/types";

interface AuthContextValue {
  user: AuthSession | null;
  isLoading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  hasPartnerRole: boolean;
}

interface AuthProviderProps {
  children: React.ReactNode;
  /**
   * Позволяет в тестах подставить заранее авторизованную сессию без походов в API.
   */
  initialSession?: AuthSession | null;
}

const STORAGE_KEY = "neft_partner_auth";

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function isPartnerRolePresent(roles: string[]): boolean {
  return roles.some((role) => role.startsWith("PARTNER_"));
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

  useEffect(() => {
    const handleUnauthorized = () => {
      logout();
    };
    window.addEventListener("partner-auth-logout", handleUnauthorized);
    return () => window.removeEventListener("partner-auth-logout", handleUnauthorized);
  }, [logout]);

  const reviveSession = useCallback(
    async (stored: AuthSession) => {
      try {
        const profile = await fetchMe(stored.token);
        if (!isPartnerRolePresent(profile.roles)) {
          setError("Эта зона доступна только партнёрам");
          logout();
          return;
        }
        const normalized: AuthSession = {
          ...stored,
          roles: profile.roles,
          email: profile.email ?? stored.email,
          subjectType: profile.subject_type,
          partnerId: profile.partner_id ?? stored.partnerId,
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

  const handleLogin = useCallback(
    async (email: string, password: string) => {
      setError(null);
      try {
        const session = await login({ email, password });
        if (!isPartnerRolePresent(session.roles)) {
          setError("У вас нет доступа к кабинету партнёра");
          logout();
          return;
        }
        const profile = await fetchMe(session.token);
        if (!isPartnerRolePresent(profile.roles)) {
          setError("У вас нет доступа к кабинету партнёра");
          logout();
          return;
        }
        const normalized: AuthSession = {
          ...session,
          email: profile.email,
          roles: profile.roles,
          subjectType: profile.subject_type,
          partnerId: profile.partner_id ?? session.partnerId,
        };
        setUser(normalized);
        persist(normalized);
      } catch (err) {
        if (err instanceof UnauthorizedError) {
          setError("Неверный email или пароль");
          return;
        }
        if (err instanceof ValidationError) {
          setError("Проверьте email и пароль");
          return;
        }
        if (err instanceof HtmlResponseError) {
          setError("Ошибка маршрутизации gateway (HTML вместо JSON)");
          return;
        }
        if (err instanceof ApiError && err.status >= 500) {
          setError("Сервис временно недоступен");
          return;
        }
        if (err instanceof TypeError) {
          setError("Сервис временно недоступен");
          return;
        }
        console.error("Ошибка авторизации", err);
        setError("Сервис временно недоступен");
      }
    },
    [logout, persist],
  );

  const value = useMemo(
    () => ({
      user,
      isLoading,
      error,
      login: handleLogin,
      logout,
      hasPartnerRole: Boolean(user?.roles && isPartnerRolePresent(user.roles)),
    }),
    [user, isLoading, error, handleLogin, logout],
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
