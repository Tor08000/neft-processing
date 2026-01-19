import React from "react";
import type { AdminPermissions } from "../types/admin";
import { useAdmin } from "./AdminContext";
import { AdminForbiddenPage } from "../pages/admin/AdminStatusPages";

type PermissionKey = keyof AdminPermissions;
type PermissionAction = "read" | "write";

interface AdminRBACGateProps {
  permission: PermissionKey;
  action?: PermissionAction;
  children: React.ReactNode;
}

export const AdminRBACGate: React.FC<AdminRBACGateProps> = ({ permission, action = "read", children }) => {
  const { profile } = useAdmin();
  const allowed = profile?.permissions?.[permission]?.[action];

  if (!allowed) {
    return <AdminForbiddenPage />;
  }

  return <>{children}</>;
};

export default AdminRBACGate;
