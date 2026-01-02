import React, { useMemo } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { hasPayoutAccess } from "../../auth/roles";

const baseNavItems = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/users", label: "Users" },
  { to: "/accounts", label: "Balances" },
  { to: "/operations", label: "Operations" },
  { to: "/fleet/cards", label: "Fleet · Cards" },
  { to: "/fleet/groups", label: "Fleet · Groups" },
  { to: "/fleet/employees", label: "Fleet · Employees" },
  { to: "/fleet/limits", label: "Fleet · Limits" },
  { to: "/fleet/spend", label: "Fleet · Spend" },
  { to: "/billing", label: "Billing" },
  { to: "/reconciliation", label: "Reconciliation" },
  { to: "/payouts", label: "Payouts" },
  { to: "/integration", label: "Integration Monitoring" },
  { to: "/analytics/risk", label: "Risk analytics" },
  { to: "/risk/rules", label: "Risk rules" },
  { to: "/crm/clients", label: "CRM · Clients" },
  { to: "/crm/contracts", label: "CRM · Contracts" },
  { to: "/crm/tariffs", label: "CRM · Tariffs" },
  { to: "/crm/subscriptions", label: "CRM · Subscriptions" },
  { to: "/subscriptions/plans", label: "Subscriptions · Plans" },
  { to: "/subscriptions/gamification", label: "Subscriptions · Gamification" },
  { to: "/money/health", label: "Money · Health" },
  { to: "/money/replay", label: "Money · Replay" },
  { to: "/explain", label: "Explain v2" },
  { to: "/cases", label: "Cases" },
  { to: "/ops/escalations", label: "Ops · Escalations" },
  { to: "/ops/kpi", label: "Ops · KPI" },
  { to: "/support/requests", label: "Support Inbox" },
  { to: "/support/cases", label: "Support Inbox · Cases" },
];

const buildContextLabel = (section: string, path: string, basePath?: string) => {
  if (!basePath) {
    return "Обзор";
  }
  const suffix = path.replace(basePath, "");
  const trail = suffix
    .split("/")
    .filter(Boolean)
    .map((segment) => decodeURIComponent(segment));
  return trail.length ? `${section} → ${trail.join(" / ")}` : `${section} → Обзор`;
};

export const Layout: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout, user } = useAuth();

  const navItems = useMemo(
    () => [
      ...baseNavItems,
      ...(user && hasPayoutAccess(user.roles) ? [{ to: "/finance/payouts", label: "Finance · Payouts" }] : []),
    ],
    [user],
  );

  const activeItem = navItems.find(
    (item) => location.pathname === item.to || location.pathname.startsWith(`${item.to}/`),
  );
  const sectionTitle = activeItem?.label ?? "Overview";
  const contextLabel = buildContextLabel(sectionTitle, location.pathname, activeItem?.to);

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="admin-layout neft-page">
      <aside className="admin-sidebar">
        <div className="admin-sidebar__title">NEFT Admin</div>
        <nav className="admin-sidebar__nav">
          {navItems.map((item) => {
            const isActive = location.pathname === item.to || location.pathname.startsWith(`${item.to}/`);
            const isSubsection = item.label.includes("·");
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`admin-nav-link${isActive ? " is-active" : ""}${isSubsection ? " is-subsection" : ""}`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <main className="admin-main">
        <header className="admin-topbar">
          <div className="admin-topbar__context">
            <div className="admin-topbar__title">{sectionTitle}</div>
            <div className="admin-topbar__subtitle">{contextLabel}</div>
          </div>
          <div className="admin-topbar__actions">
            <div>
              <div className="admin-user__email">{user?.email}</div>
              <div className="admin-user__roles">{user?.roles.join(", ")}</div>
            </div>
            <button onClick={handleLogout} className="neft-btn-secondary" type="button">
              Выход
            </button>
          </div>
        </header>
        <div className="admin-content">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

export default Layout;
