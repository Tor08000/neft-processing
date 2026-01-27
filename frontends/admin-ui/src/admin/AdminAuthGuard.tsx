import React from "react";
import { Outlet } from "react-router-dom";
import { useAdmin } from "./AdminContext";
import {
  AdminForbiddenPage,
  AdminLoadingPage,
  AdminMisconfigPage,
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
      return <AdminUnauthorizedPage requestId={error.request_id ?? undefined} errorId={error.error ?? undefined} />;
    }
    if (error?.error === "admin_forbidden") {
      return <AdminForbiddenPage requestId={error.request_id ?? undefined} errorId={error.error ?? undefined} />;
    }
    const status = error?.status;
    if (import.meta.env.DEV && status === 404) {
      return <AdminMisconfigPage requestId={error?.request_id ?? undefined} errorId={error?.error ?? undefined} />;
    }
    const message = status && status >= 500 ? "Service unavailable" : undefined;
    return (
      <AdminTechErrorPage
        requestId={error?.request_id ?? undefined}
        errorId={error?.error ?? undefined}
        message={message}
      />
    );
  }

  return <Outlet />;
};

export default AdminAuthGuard;
