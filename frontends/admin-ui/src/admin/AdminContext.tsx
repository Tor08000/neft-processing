import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { verifyAdminAuth } from "../api/adminAuth";
import { fetchAdminMe, AdminMeError } from "../api/adminMe";
import { ApiError, ForbiddenError, UnauthorizedError } from "../api/http";
import type { AdminErrorPayload, AdminMeResponse } from "../types/admin";
import { useAuth } from "../auth/AuthContext";
import { hasAdminRole } from "../auth/roles";

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
    verifyAdminAuth(accessToken)
      .then(() => fetchAdminMe(accessToken))
      .then((data) => {
        if (cancelled) return;
        if (!hasAdminRole(data.admin_user.roles)) {
          setProfile(null);
          setError({ error: "admin_forbidden", message: "Forbidden", status: 403 });
          return;
        }
        setProfile(data);
        setError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof UnauthorizedError) {
          setError({ error: "admin_unauthorized", message: "Unauthorized", status: 401 });
          logout();
        } else if (err instanceof ForbiddenError) {
          setError({ error: "admin_forbidden", message: "Forbidden", status: 403 });
        } else if (err instanceof AdminMeError) {
          const payload = err.payload ?? { error: "admin_error", message: err.message, status: err.status };
          setError(payload);
          if (err.status === 401) {
            logout();
          }
        } else if (err instanceof ApiError) {
          setError({
            error: err.errorCode ?? "admin_error",
            message: err.message,
            status: err.status,
            request_id: err.requestId ?? err.correlationId,
          });
        } else if (err instanceof TypeError) {
          setError({ error: "admin_network", message: "Network error", status: 0 });
        } else {
          setError({ error: "admin_error", message: "Admin bootstrap failed", status: 500 });
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
