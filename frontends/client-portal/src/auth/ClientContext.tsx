import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ClientMeResponse } from "../api/clientPortal";
import { fetchClientMe } from "../api/clientPortal";
import { ApiError, UnauthorizedError } from "../api/http";
import { useAuth } from "./AuthContext";

type ClientContextValue = {
  client: ClientMeResponse | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
};

const ClientContext = createContext<ClientContextValue | undefined>(undefined);

export function ClientProvider({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const [client, setClient] = useState<ClientMeResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadClient = useCallback(async () => {
    if (!user) {
      setClient(null);
      setError(null);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchClientMe(user);
      setClient(data);
    } catch (err) {
      if (err instanceof UnauthorizedError) {
        logout();
        return;
      }
      if (err instanceof ApiError && err.status === 403) {
        setError("Нет доступа к клиентскому профилю");
        return;
      }
      console.error("Не удалось загрузить профиль клиента", err);
      setError("Профиль клиента временно недоступен");
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
      refresh: loadClient,
    }),
    [client, error, isLoading, loadClient],
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
