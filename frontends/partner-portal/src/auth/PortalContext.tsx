import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { fetchPortalMe } from "../api/portal";
import type { PortalMeResponse } from "../api/types";
import { ApiError, UnauthorizedError } from "../api/http";
import { useAuth } from "./AuthContext";

export type PortalState =
  | "AUTH_REQUIRED"
  | "LOADING"
  | "READY"
  | "NO_SUBSCRIPTION"
  | "NO_MODULES_ENABLED"
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

const extractModules = (portal: PortalMeResponse | null): unknown[] | null => {
  if (!portal) return null;
  const candidate =
    (portal as { modules?: unknown }).modules ??
    (portal.subscription as { modules?: unknown } | null | undefined)?.modules ??
    (portal.entitlements_snapshot as { modules?: unknown } | null | undefined)?.modules;
  if (Array.isArray(candidate)) {
    return candidate;
  }
  if (candidate && typeof candidate === "object") {
    const entries = Object.values(candidate as Record<string, unknown>);
    return entries.length === 0 ? [] : null;
  }
  return null;
};

const resolvePortalState = (portal: PortalMeResponse): PortalState => {
  if (!portal.subscription) {
    return "NO_SUBSCRIPTION";
  }
  const modules = extractModules(portal);
  if (modules && modules.length === 0) {
    return "NO_MODULES_ENABLED";
  }
  return "READY";
};

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
      const data = await fetchPortalMe(user);
      setPortal(data);
      setPortalState(resolvePortalState(data));
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
