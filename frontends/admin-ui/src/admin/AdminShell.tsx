import React from "react";
import { Outlet, useLocation } from "react-router-dom";
import {
  AuditIcon,
  BrandHeader,
  BrandSidebar,
  BriefcaseIcon,
  ChartIcon,
  DashboardIcon,
  FileIcon,
  LogisticsIcon,
  PageShell,
  ShieldIcon,
  UsersIcon,
  WalletIcon,
  WorkflowIcon,
} from "@shared/brand/components";
import { useAdmin } from "./AdminContext";
import { AdminEnvBadge } from "../components/admin/AdminEnvBadge";
import type { AdminPermissionKey } from "../types/admin";

type NavItem = {
  key: string;
  label: string;
  to: string;
  permissionKey?: AdminPermissionKey;
  activePrefix?: string;
};

const NAV_ITEMS: NavItem[] = [
  { key: "home", label: "Home", to: "/" },
  { key: "admins", label: "Admins", to: "/admins", permissionKey: "access" },
  { key: "cases", label: "Cases", to: "/cases", permissionKey: "cases" },
  { key: "finance", label: "Finance", to: "/finance", permissionKey: "finance", activePrefix: "/finance" },
  { key: "revenue", label: "Revenue", to: "/finance/revenue", permissionKey: "revenue", activePrefix: "/finance/revenue" },
  { key: "commercial", label: "Commercial", to: "/commercial", permissionKey: "commercial" },
  { key: "crm", label: "CRM", to: "/crm/clients", permissionKey: "crm", activePrefix: "/crm" },
  { key: "marketplace", label: "Marketplace", to: "/marketplace/moderation", permissionKey: "marketplace", activePrefix: "/marketplace" },
  { key: "onboarding", label: "Onboarding", to: "/invitations", permissionKey: "onboarding" },
  { key: "ops", label: "Ops", to: "/ops", permissionKey: "ops", activePrefix: "/ops" },
  { key: "logistics", label: "Logistics", to: "/logistics/inspection", permissionKey: "ops" },
  { key: "runtime", label: "Runtime", to: "/runtime", permissionKey: "runtime" },
  { key: "geo", label: "Geo Analytics", to: "/geo", permissionKey: "ops" },
  { key: "rules", label: "Rules Sandbox", to: "/rules/sandbox", permissionKey: "ops", activePrefix: "/rules" },
  { key: "risk-rules", label: "Risk Rules", to: "/risk/rules", permissionKey: "ops", activePrefix: "/risk/rules" },
  { key: "policies", label: "Policy Center", to: "/policies", permissionKey: "ops", activePrefix: "/policies" },
  { key: "legal", label: "Legal", to: "/legal/documents", permissionKey: "legal", activePrefix: "/legal" },
  { key: "audit", label: "Audit", to: "/audit", permissionKey: "audit" },
];

const NAV_ICONS: Record<string, JSX.Element> = {
  home: <DashboardIcon size={18} />,
  admins: <UsersIcon size={18} />,
  cases: <WorkflowIcon size={18} />,
  finance: <WalletIcon size={18} />,
  revenue: <ChartIcon size={18} />,
  commercial: <BriefcaseIcon size={18} />,
  crm: <UsersIcon size={18} />,
  marketplace: <ShieldIcon size={18} />,
  onboarding: <FileIcon size={18} />,
  ops: <WorkflowIcon size={18} />,
  logistics: <LogisticsIcon size={18} />,
  runtime: <ChartIcon size={18} />,
  geo: <ChartIcon size={18} />,
  rules: <ShieldIcon size={18} />,
  "risk-rules": <ShieldIcon size={18} />,
  policies: <WorkflowIcon size={18} />,
  legal: <FileIcon size={18} />,
  audit: <AuditIcon size={18} />,
};

const getActivePrefix = (item: NavItem) => item.activePrefix ?? item.to;

const matchesNavItem = (item: NavItem, pathname: string) => {
  if (item.to === "/") return pathname === "/";
  const prefix = getActivePrefix(item);
  return pathname === prefix || pathname.startsWith(`${prefix}/`);
};

export const AdminShell: React.FC = () => {
  const location = useLocation();
  const { profile } = useAdmin();
  const permissions = profile?.permissions;
  const readOnly = profile?.read_only ?? false;
  const availableItems = NAV_ITEMS.filter(
    (item) => !item.permissionKey || permissions?.[item.permissionKey]?.read,
  ).map((item) => ({
    ...item,
    hint: readOnly ? "read-only" : undefined,
  }));
  const activeItem = [...availableItems]
    .sort((left, right) => getActivePrefix(right).length - getActivePrefix(left).length)
    .find((item) => matchesNavItem(item, location.pathname));

  return (
    <div className="brand-shell brand-shell--admin neft-page neft-app admin-shell">
      <BrandSidebar
        items={availableItems.map((item) => ({
          ...item,
          icon: NAV_ICONS[item.key] ?? <DashboardIcon size={18} />,
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
              {readOnly ? <span className="neft-chip neft-chip-warn">READ-ONLY</span> : null}
                <div className="admin-shell__user">
                  <div className="admin-shell__email">{profile?.admin_user?.email ?? "—"}</div>
                  <div className="admin-shell__roles">
                    {(profile?.role_levels?.join(" · ") || profile?.admin_user?.roles.join(", ")) ?? "—"}
                  </div>
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
