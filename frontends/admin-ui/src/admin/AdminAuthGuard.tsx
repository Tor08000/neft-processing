import React from "react";
import { Outlet } from "react-router-dom";
import { useAdmin } from "./AdminContext";
import {
  AdminForbiddenPage,
  AdminLoadingPage,
  AdminTechErrorPage,
  AdminUnauthorizedPage,
} from "../pages/admin/AdminStatusPages";

export const AdminAuthGuard: React.FC = () => {
  const { profile, isLoading, error } = useAdmin();

  if (isLoading) {
    return <AdminLoadingPage />;
  }

  if (!profile) {
    if (error?.error === "admin_unauthorized") {
      return <AdminUnauthorizedPage requestId={error.request_id ?? undefined} />;
    }
    if (error?.error === "admin_forbidden") {
      return <AdminForbiddenPage requestId={error.request_id ?? undefined} />;
    }
    const status = error?.status;
    const message =
      status && status >= 500
        ? "Service unavailable"
        : import.meta.env.DEV && status === 404
          ? "api route misconfigured"
          : undefined;
    return <AdminTechErrorPage requestId={error?.request_id ?? undefined} message={message} />;
  }

  return <Outlet />;
};

export default AdminAuthGuard;
