import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ForbiddenPage } from "../pages/ForbiddenPage";

export function ProtectedRoute() {
  const { user, isLoading, hasPartnerRole, logout } = useAuth();
  const location = useLocation();
  const returnUrl = `${location.pathname}${location.search}`;

  if (isLoading) {
    return <div className="centered">Загружаем сессию...</div>;
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

  return <Outlet />;
}
