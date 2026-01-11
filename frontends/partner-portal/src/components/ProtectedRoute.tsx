import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ForbiddenPage } from "../pages/ForbiddenPage";
import { useLegalGate } from "../auth/LegalGateContext";
import { LoadingState } from "./states";

export function ProtectedRoute() {
  const { user, isLoading, hasPartnerRole, logout } = useAuth();
  const { isBlocked } = useLegalGate();
  const location = useLocation();
  const returnUrl = `${location.pathname}${location.search}`;

  if (isLoading) {
    return <LoadingState label="Загружаем сессию..." />;
  }

  if (!user) {
    return <Navigate to={`/login?returnUrl=${encodeURIComponent(returnUrl)}`} replace />;
  }

  if (user.expiresAt <= Date.now()) {
    logout();
    return <Navigate to={`/login?returnUrl=${encodeURIComponent(returnUrl)}`} replace />;
  }

  if (!hasPartnerRole) {
    return <ForbiddenPage />;
  }

  if (isBlocked && location.pathname !== "/legal") {
    return <Navigate to="/legal" replace />;
  }

  return <Outlet />;
}
