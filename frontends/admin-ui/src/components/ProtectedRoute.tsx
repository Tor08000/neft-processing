import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { hasPayoutAccess } from "../auth/roles";
import { useLegalGate } from "../auth/LegalGateContext";

export function ProtectedRoute() {
  const { user, isLoading, isAdmin } = useAuth();
  const { isBlocked } = useLegalGate();
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

  if (isBlocked && location.pathname !== "/legal") {
    return <Navigate to="/legal" replace />;
  }

  return <Outlet />;
}
