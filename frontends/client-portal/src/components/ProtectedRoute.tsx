import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useClient } from "../auth/ClientContext";
import { ForbiddenPage } from "../pages/ForbiddenPage";
import { useLegalGate } from "../auth/LegalGateContext";

export function ProtectedRoute() {
  const { user, authStatus, hasClientRole } = useAuth();
  const { client, isLoading: isClientLoading } = useClient();
  const { isBlocked } = useLegalGate();
  const location = useLocation();
  const returnUrl = `${location.pathname}${location.search}`;

  if (authStatus === "loading") {
    return <div className="centered">Загружаем сессию...</div>;
  }

  if (authStatus !== "authenticated" || !user) {
    return <Navigate to={`/login?returnUrl=${encodeURIComponent(returnUrl)}`} replace />;
  }

  if (!hasClientRole) {
    return <ForbiddenPage />;
  }

  if (isClientLoading) {
    return <div className="centered">Загружаем профиль...</div>;
  }

  if (isBlocked && location.pathname !== "/legal") {
    return <Navigate to="/legal" replace />;
  }

  return <Outlet />;
}
