import React from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAdmin } from "./AdminContext";
import { AdminForbiddenPage, AdminLoadingPage, AdminUnauthorizedPage } from "../pages/admin/AdminStatusPages";

export const AdminAuthGuard: React.FC = () => {
  const { profile, isLoading, error } = useAdmin();

  if (isLoading) {
    return <AdminLoadingPage />;
  }

  if (!profile) {
    if (error?.error === "admin_unauthorized") {
      return <Navigate to="/login" replace />;
    }
    if (error?.error === "admin_forbidden") {
      return <AdminForbiddenPage requestId={error.request_id ?? undefined} />;
    }
    return <AdminUnauthorizedPage requestId={error?.request_id ?? undefined} />;
  }

  return <Outlet />;
};

export default AdminAuthGuard;
