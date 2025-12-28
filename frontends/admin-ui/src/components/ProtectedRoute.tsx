import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { hasPayoutAccess } from "../auth/roles";

export function ProtectedRoute() {
  const { user, isLoading, isAdmin } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <div className="centered">Загружаем сессию...</div>;
  }

  if (!user || !isAdmin) {
    return <Navigate to="/login" replace />;
  }

  if (location.pathname.startsWith("/finance/payouts") && !hasPayoutAccess(user.roles)) {
    return <Navigate to="/forbidden" replace />;
  }

  return <Outlet />;
}
