import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { fetchAdminMe, AdminMeError } from "../api/adminMe";
import type { AdminErrorPayload, AdminMeResponse } from "../types/admin";
import { useAuth } from "../auth/AuthContext";

interface AdminContextValue {
  profile: AdminMeResponse | null;
  isLoading: boolean;
  error: AdminErrorPayload | null;
}

const AdminContext = createContext<AdminContextValue | undefined>(undefined);

export const AdminProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const { accessToken, isLoading: authLoading, logout } = useAuth();
  const [profile, setProfile] = useState<AdminMeResponse | null>(null);
  const [error, setError] = useState<AdminErrorPayload | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (authLoading) {
      setIsLoading(true);
      return;
    }
    if (!accessToken) {
      setProfile(null);
      setError({ error: "admin_unauthorized", message: "Unauthorized" });
      setIsLoading(false);
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    fetchAdminMe(accessToken)
      .then((data) => {
        if (cancelled) return;
        setProfile(data);
        setError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof AdminMeError) {
          setError(err.payload ?? { error: "admin_error", message: err.message });
          if (err.status === 401) {
            logout();
          }
        } else {
          setError({ error: "admin_error", message: "Admin bootstrap failed" });
        }
        setProfile(null);
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [accessToken, authLoading, logout]);

  const value = useMemo(
    () => ({
      profile,
      isLoading,
      error,
    }),
    [profile, isLoading, error],
  );

  return <AdminContext.Provider value={value}>{children}</AdminContext.Provider>;
};

export function useAdmin() {
  const ctx = useContext(AdminContext);
  if (!ctx) {
    throw new Error("useAdmin must be used within AdminProvider");
  }
  return ctx;
}
