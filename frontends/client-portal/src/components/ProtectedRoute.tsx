import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useClient } from "../auth/ClientContext";
import { ForbiddenPage } from "../pages/ForbiddenPage";
import { useLegalGate } from "../auth/LegalGateContext";

export function ProtectedRoute() {
  const { user, isLoading, hasClientRole, logout } = useAuth();
  const { client, isLoading: isClientLoading } = useClient();
  const { isBlocked } = useLegalGate();
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

  if (!hasClientRole) {
    return <ForbiddenPage />;
  }

  if (isClientLoading) {
    return <div className="centered">Загружаем профиль...</div>;
  }

  const onboardingEnabled = client?.gating?.onboarding_enabled ?? client?.features?.onboarding_enabled ?? true;
  if (
    onboardingEnabled &&
    client?.access_state &&
    ["NEEDS_ONBOARDING", "NEEDS_PLAN", "NEEDS_CONTRACT"].includes(client.access_state) &&
    !location.pathname.startsWith("/onboarding")
  ) {
    return <Navigate to="/onboarding" replace />;
  }

  if (isBlocked && location.pathname !== "/legal") {
    return <Navigate to="/legal" replace />;
  }

  return <Outlet />;
}
