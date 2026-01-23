import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { PortalMeResponse } from "../api/clientPortal";
import { fetchClientMe } from "../api/clientPortal";
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

type ClientContextValue = {
  client: PortalMeResponse | null;
  isLoading: boolean;
  error: string | null;
  portalState: PortalState;
  refresh: () => Promise<void>;
};

const ClientContext = createContext<ClientContextValue | undefined>(undefined);

const extractModules = (client: PortalMeResponse | null): unknown[] | null => {
  if (!client) return null;
  const candidate =
    (client as { modules?: unknown }).modules ??
    (client.subscription as { modules?: unknown } | null | undefined)?.modules ??
    (client.entitlements_snapshot as { modules?: unknown } | null | undefined)?.modules;
  if (Array.isArray(candidate)) {
    return candidate;
  }
  if (candidate && typeof candidate === "object") {
    const entries = Object.values(candidate as Record<string, unknown>);
    return entries.length === 0 ? [] : null;
  }
  return null;
};

const resolvePortalState = (client: PortalMeResponse): PortalState => {
  if (!client.subscription) {
    return "NO_SUBSCRIPTION";
  }
  const modules = extractModules(client);
  if (modules && modules.length === 0) {
    return "NO_MODULES_ENABLED";
  }
  return "READY";
};

export function ClientProvider({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const [client, setClient] = useState<PortalMeResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [portalState, setPortalState] = useState<PortalState>("LOADING");

  const loadClient = useCallback(async () => {
    if (!user) {
      setClient(null);
      setError(null);
      setPortalState("AUTH_REQUIRED");
      return;
    }
    setIsLoading(true);
    setError(null);
    setPortalState("LOADING");
    try {
      const data = await fetchClientMe(user);
      setClient(data);
      setPortalState(resolvePortalState(data));
    } catch (err) {
      if (err instanceof UnauthorizedError) {
        setPortalState("AUTH_REQUIRED");
        logout();
        return;
      }
      if (err instanceof ApiError && err.status === 403) {
        setError("Нет доступа к клиентскому профилю");
        setPortalState("ERROR_FATAL");
        return;
      }
      if (err instanceof ApiError && (err.status === 502 || err.status === 503)) {
        setError("Профиль клиента временно недоступен");
        setPortalState("SERVICE_UNAVAILABLE");
        return;
      }
      console.error("Не удалось загрузить профиль клиента", err);
      setError("Профиль клиента временно недоступен");
      setPortalState("ERROR_FATAL");
    } finally {
      setIsLoading(false);
    }
  }, [logout, user]);

  useEffect(() => {
    void loadClient();
  }, [loadClient]);

  const value = useMemo(
    () => ({
      client,
      isLoading,
      error,
      portalState,
      refresh: loadClient,
    }),
    [client, error, isLoading, loadClient, portalState],
  );

  return <ClientContext.Provider value={value}>{children}</ClientContext.Provider>;
}

export function useClient() {
  const ctx = useContext(ClientContext);
  if (!ctx) {
    throw new Error("useClient must be used within ClientProvider");
  }
  return ctx;
}
