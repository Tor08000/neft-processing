import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { fetchPortalMe } from "../api/portal";
import type { PortalMeResponse } from "../api/types";
import { ApiError, UnauthorizedError } from "../api/http";
import { useAuth } from "./AuthContext";

interface PortalContextValue {
  portal: PortalMeResponse | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

const PortalContext = createContext<PortalContextValue | undefined>(undefined);

export function PortalProvider({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const [portal, setPortal] = useState<PortalMeResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadPortal = useCallback(async () => {
    if (!user) {
      setPortal(null);
      setError(null);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchPortalMe(user);
      setPortal(data);
    } catch (err) {
      if (err instanceof UnauthorizedError) {
        logout();
        return;
      }
      if (err instanceof ApiError && err.status === 403) {
        setError("Нет доступа к порталу");
        return;
      }
      console.error("Не удалось загрузить portal/me", err);
      setError("Портал временно недоступен");
    } finally {
      setIsLoading(false);
    }
  }, [logout, user]);

  useEffect(() => {
    void loadPortal();
  }, [loadPortal]);

  const value = useMemo(
    () => ({
      portal,
      isLoading,
      error,
      refresh: loadPortal,
    }),
    [portal, isLoading, error, loadPortal],
  );

  return <PortalContext.Provider value={value}>{children}</PortalContext.Provider>;
}

export function usePortal() {
  const ctx = useContext(PortalContext);
  if (!ctx) {
    throw new Error("usePortal must be used within PortalProvider");
  }
  return ctx;
}
