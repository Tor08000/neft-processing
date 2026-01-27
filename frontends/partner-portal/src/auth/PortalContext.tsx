import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { fetchPortalMe, verifyPartnerAuth } from "../api/portal";
import type { PortalMeResponse } from "../api/types";
import { ApiError, UnauthorizedError } from "../api/http";
import { useAuth } from "./AuthContext";

export type PortalState =
  | "AUTH_REQUIRED"
  | "LOADING"
  | "READY"
  | "SERVICE_UNAVAILABLE"
  | "ERROR_FATAL";

interface PortalContextValue {
  portal: PortalMeResponse | null;
  isLoading: boolean;
  error: string | null;
  portalState: PortalState;
  refresh: () => Promise<void>;
}

const PortalContext = createContext<PortalContextValue | undefined>(undefined);

export function PortalProvider({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const [portal, setPortal] = useState<PortalMeResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [portalState, setPortalState] = useState<PortalState>("LOADING");

  const loadPortal = useCallback(async () => {
    if (!user) {
      setPortal(null);
      setError(null);
      setPortalState("AUTH_REQUIRED");
      return;
    }
    setIsLoading(true);
    setError(null);
    setPortalState("LOADING");
    try {
      await verifyPartnerAuth(user);
      const data = await fetchPortalMe(user);
      setPortal(data);
      setPortalState("READY");
    } catch (err) {
      if (err instanceof UnauthorizedError) {
        setPortalState("AUTH_REQUIRED");
        logout();
        return;
      }
      if (err instanceof ApiError && err.status === 403) {
        setError("Нет доступа к порталу");
        setPortalState("ERROR_FATAL");
        return;
      }
      if (err instanceof ApiError && (err.status === 502 || err.status === 503)) {
        setError("Портал временно недоступен");
        setPortalState("SERVICE_UNAVAILABLE");
        return;
      }
      console.error("Не удалось загрузить portal/me", err);
      setError("Портал временно недоступен");
      setPortalState("ERROR_FATAL");
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
      portalState,
      refresh: loadPortal,
    }),
    [portal, isLoading, error, loadPortal, portalState],
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
