import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { PortalMeResponse } from "../api/clientPortal";
import { fetchClientMe, PORTAL_ME_PATH } from "../api/clientPortal";
import { ApiError, HtmlResponseError, UnauthorizedError } from "../api/http";
import { CORE_API_BASE } from "../api/base";
import { useAuth } from "./AuthContext";

export type PortalState =
  | "AUTH_REQUIRED"
  | "LOADING"
  | "READY"
  | "NO_SUBSCRIPTION"
  | "NO_MODULES_ENABLED"
  | "FORBIDDEN"
  | "SERVICE_UNAVAILABLE"
  | "NETWORK_DOWN"
  | "API_MISCONFIGURED"
  | "ERROR_FATAL";

export type PortalError = {
  kind: "AUTH" | "BILLING" | "ENTITLEMENT" | "UPSTREAM" | "MISCONFIG" | "NETWORK";
  status?: number;
  path?: string;
  requestId?: string;
  message?: string;
};

type ClientContextValue = {
  client: PortalMeResponse | null;
  isLoading: boolean;
  error: PortalError | null;
  portalState: PortalState;
  refresh: () => Promise<void>;
};

const ClientContext = createContext<ClientContextValue | undefined>(undefined);
const STORAGE_KEY = "neft_client_portal";

const readStoredPortal = (): PortalMeResponse | null => {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as PortalMeResponse;
  } catch (err) {
    console.warn("Не удалось прочитать сохраненный portal/me", err);
    return null;
  }
};

const persistPortal = (portal: PortalMeResponse | null) => {
  if (!portal) {
    localStorage.removeItem(STORAGE_KEY);
    return;
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(portal));
};

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

const PORTAL_ME_URL = `${CORE_API_BASE}${PORTAL_ME_PATH}`;

const resolvePortalError = (err: unknown): { portalState: PortalState; error: PortalError } => {
  if (err instanceof ApiError) {
    if (err.status === 402 || err.status === 403) {
      const isBilling =
        err.status === 402 ||
        err.errorCode?.includes("billing") ||
        err.errorCode?.includes("subscription") ||
        err.errorCode?.includes("plan");
      return {
        portalState: "FORBIDDEN",
        error: {
          kind: isBilling ? "BILLING" : "ENTITLEMENT",
          status: err.status,
          path: PORTAL_ME_URL,
          requestId: err.requestId ?? undefined,
          message: err.errorCode ?? err.message,
        },
      };
    }
    if (err.status === 404) {
      return {
        portalState: "API_MISCONFIGURED",
        error: {
          kind: "MISCONFIG",
          status: err.status,
          path: PORTAL_ME_URL,
          requestId: err.requestId ?? undefined,
          message: err.message,
        },
      };
    }
    if (err.status === 502 || err.status === 503) {
      return {
        portalState: "SERVICE_UNAVAILABLE",
        error: {
          kind: "UPSTREAM",
          status: err.status,
          path: PORTAL_ME_URL,
          requestId: err.requestId ?? undefined,
          message: err.message,
        },
      };
    }
    return {
      portalState: "ERROR_FATAL",
      error: {
        kind: "UPSTREAM",
        status: err.status,
        path: PORTAL_ME_URL,
        requestId: err.requestId ?? undefined,
        message: err.message,
      },
    };
  }
  if (err instanceof HtmlResponseError) {
    if (err.status === 404) {
      return {
        portalState: "API_MISCONFIGURED",
        error: {
          kind: "MISCONFIG",
          status: err.status,
          path: err.url ?? PORTAL_ME_URL,
          message: err.message,
        },
      };
    }
    return {
      portalState: "SERVICE_UNAVAILABLE",
      error: {
        kind: "UPSTREAM",
        status: err.status,
        path: err.url ?? PORTAL_ME_URL,
        message: err.message,
      },
    };
  }
  if (err instanceof TypeError) {
    return {
      portalState: "NETWORK_DOWN",
      error: {
        kind: "NETWORK",
        path: PORTAL_ME_URL,
        message: err.message,
      },
    };
  }
  return {
    portalState: "ERROR_FATAL",
    error: {
      kind: "UPSTREAM",
      path: PORTAL_ME_URL,
      message: err instanceof Error ? err.message : "Unknown error",
    },
  };
};

export function ClientProvider({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const [client, setClient] = useState<PortalMeResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<PortalError | null>(null);
  const [portalState, setPortalState] = useState<PortalState>("LOADING");

  const loadClient = useCallback(async () => {
    if (!user) {
      setClient(null);
      setError(null);
      setPortalState("AUTH_REQUIRED");
      persistPortal(null);
      return;
    }
    setIsLoading(true);
    setError(null);
    setPortalState("LOADING");
    try {
      const data = await fetchClientMe(user);
      setClient(data);
      setPortalState(resolvePortalState(data));
      persistPortal(data);
    } catch (err) {
      if (err instanceof UnauthorizedError) {
        setPortalState("AUTH_REQUIRED");
        logout();
        return;
      }
      const resolved = resolvePortalError(err);
      if (resolved.portalState === "SERVICE_UNAVAILABLE" || resolved.portalState === "NETWORK_DOWN") {
        const cached = readStoredPortal();
        if (cached) {
          setClient(cached);
          setPortalState(resolvePortalState(cached));
          return;
        }
      }
      const cached = readStoredPortal();
      if (cached) {
        setClient(cached);
        setPortalState(resolvePortalState(cached));
        return;
      }
      console.error("Не удалось загрузить профиль клиента", err);
      setError(resolved.error);
      setPortalState(resolved.portalState);
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
