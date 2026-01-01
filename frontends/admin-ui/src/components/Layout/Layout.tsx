import React from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { hasPayoutAccess } from "../../auth/roles";

const navItems = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/users", label: "Users" },
  { to: "/accounts", label: "Balances" },
  { to: "/operations", label: "Operations" },
  { to: "/billing", label: "Billing" },
  { to: "/payouts", label: "Payouts" },
  { to: "/integration", label: "Integration Monitoring" },
  { to: "/analytics/risk", label: "Risk analytics" },
  { to: "/risk/rules", label: "Risk rules" },
];

export const Layout: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout, user } = useAuth();
  const navItems = [
    { to: "/dashboard", label: "Dashboard" },
    { to: "/users", label: "Users" },
    { to: "/accounts", label: "Balances" },
    { to: "/operations", label: "Operations" },
    { to: "/billing", label: "Billing" },
    { to: "/integration", label: "Integration Monitoring" },
    { to: "/analytics/risk", label: "Risk analytics" },
    { to: "/risk/rules", label: "Risk rules" },
    { to: "/crm/clients", label: "CRM · Clients" },
    { to: "/crm/contracts", label: "CRM · Contracts" },
    { to: "/crm/tariffs", label: "CRM · Tariffs" },
    { to: "/crm/subscriptions", label: "CRM · Subscriptions" },
    { to: "/money/health", label: "Money · Health" },
    { to: "/money/replay", label: "Money · Replay" },
    { to: "/explain", label: "Unified Explain" },
    { to: "/ops/escalations", label: "Ops · Escalations" },
    { to: "/ops/kpi", label: "Ops · KPI" },
    { to: "/support/requests", label: "Support Inbox" },
    ...(user && hasPayoutAccess(user.roles) ? [{ to: "/finance/payouts", label: "Finance · Payouts" }] : []),
  ];

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
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`admin-nav-link${isActive ? " is-active" : ""}`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <main className="admin-main">
        <header className="admin-topbar">
          <div>
            <div className="admin-user__email">{user?.email}</div>
            <div className="admin-user__roles">{user?.roles.join(", ")}</div>
          </div>
          <button onClick={handleLogout} className="neft-btn-secondary" type="button">
            Выход
          </button>
        </header>
        <div className="admin-content">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

export default Layout;
