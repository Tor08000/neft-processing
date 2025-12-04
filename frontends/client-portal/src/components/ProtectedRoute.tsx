import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export function ProtectedRoute() {
  const { user, isLoading, hasClientRole } = useAuth();

  if (isLoading) {
    return <div className="centered">Загружаем сессию...</div>;
  }

  if (!user || !hasClientRole) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
