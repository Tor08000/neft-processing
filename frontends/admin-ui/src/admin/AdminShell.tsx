import React from "react";
import { Outlet, useLocation } from "react-router-dom";
import { BrandHeader, BrandSidebar, PageShell } from "@shared/brand/components";
import { useAdmin } from "./AdminContext";
import { AdminEnvBadge } from "../components/admin/AdminEnvBadge";

const NAV_ITEMS = [
  { key: "ops", label: "Ops", to: "/ops" },
  { key: "finance", label: "Finance", to: "/finance" },
  { key: "sales", label: "Sales", to: "/sales" },
  { key: "legal", label: "Legal", to: "/legal" },
  { key: "audit", label: "Audit", to: "/audit" },
];

export const AdminShell: React.FC = () => {
  const location = useLocation();
  const { profile } = useAdmin();
  const permissions = profile?.permissions;
  const availableItems = NAV_ITEMS.filter((item) => permissions?.[item.key as keyof typeof permissions]?.read);
  const activeItem = availableItems.find(
    (item) => location.pathname === item.to || location.pathname.startsWith(`${item.to}/`),
  );

  return (
    <div className="brand-shell neft-page neft-app admin-shell">
      <BrandSidebar
        items={availableItems.map((item) => ({
          ...item,
          icon: <span aria-hidden>◆</span>,
        }))}
        title="Admin"
      />
      <main className="brand-main">
        <BrandHeader
          title={activeItem?.label ?? "Admin"}
          subtitle={profile?.admin_user?.email ?? ""}
          userSlot={
            <div className="admin-shell__header">
              {profile?.env && <AdminEnvBadge envName={profile.env.name} />}
              <div className="admin-shell__user">
                <div className="admin-shell__email">{profile?.admin_user?.email ?? "—"}</div>
                <div className="admin-shell__roles">{profile?.admin_user?.roles.join(", ")}</div>
              </div>
            </div>
          }
        />
        <div className="brand-content">
          <PageShell key={location.pathname}>
            <Outlet />
          </PageShell>
        </div>
      </main>
    </div>
  );
};

export default AdminShell;
