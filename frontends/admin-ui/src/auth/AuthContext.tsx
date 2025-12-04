import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { login as apiLogin, me } from "../api/auth";
import { ForbiddenError, UnauthorizedError, ValidationError } from "../api/http";
import type { AuthSession, AuthUser } from "../types/auth";

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

const STORAGE_KEY = "neft_admin_auth";

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const ADMIN_ROLES = ["ADMIN", "SUPERADMIN", "PLATFORM_ADMIN"] as const;

function hasAdminRole(roles: string[]): boolean {
  return roles.some((role) => ADMIN_ROLES.includes(role as (typeof ADMIN_ROLES)[number]));
}

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
        const profile = await me(stored.accessToken);
        if (!hasAdminRole(profile.roles)) {
          setError("У вас нет прав доступа к админской панели");
          logout();
          return;
        }
        const normalized: AuthUser = {
          id: profile.id,
          email: profile.email,
          roles: profile.roles,
          subjectType: profile.subjectType,
        };
        setUser(normalized);
        setRoles(profile.roles);
        setAccessToken(stored.accessToken);
        persist({ ...stored, roles: profile.roles, email: profile.email });
      } catch (err) {
        if (err instanceof UnauthorizedError) {
          logout();
        }
      } finally {
        setIsLoading(false);
      }
    },
    [logout],
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
        const profile = await me(session.accessToken);
        if (!hasAdminRole(profile.roles)) {
          setError("У вас нет прав доступа к админской панели");
          logout();
          return;
        }
        const normalized: AuthUser = {
          id: profile.id,
          email: profile.email,
          roles: profile.roles,
          subjectType: profile.subjectType,
        };
        setUser(normalized);
        setAccessToken(session.accessToken);
        setRoles(profile.roles);
        persist({ ...session, email: profile.email, roles: profile.roles });
      } catch (err) {
        if (err instanceof UnauthorizedError) {
          setError("Неверный логин или пароль");
          return;
        }
        if (err instanceof ForbiddenError) {
          setError("У вас нет прав доступа к админской панели");
          return;
        }
        if (err instanceof ValidationError) {
          setError("Проверьте введённые данные");
          return;
        }
        console.error("Ошибка авторизации", err);
        setError("Ошибка авторизации, попробуйте позже");
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
