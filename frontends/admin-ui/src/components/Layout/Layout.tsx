import React from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";

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

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <aside
        style={{
          width: 240,
          background: "#0f172a",
          color: "#e2e8f0",
          padding: "20px 16px",
        }}
      >
        <div style={{ fontWeight: 800, fontSize: 18, marginBottom: 24 }}>NEFT Admin</div>
        <nav style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {navItems.map((item) => {
            const isActive = location.pathname === item.to || location.pathname.startsWith(`${item.to}/`);
            return (
              <Link
                key={item.to}
                to={item.to}
                style={{
                  padding: "10px 12px",
                  borderRadius: 10,
                  textDecoration: "none",
                  color: isActive ? "#0f172a" : "#e2e8f0",
                  background: isActive ? "#e2e8f0" : "transparent",
                  fontWeight: 600,
                }}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <main style={{ flex: 1, background: "#f8fafc" }}>
        <header
          style={{
            display: "flex",
            justifyContent: "space-between",
            padding: "16px 24px",
            background: "#fff",
            borderBottom: "1px solid #e2e8f0",
          }}
        >
          <div>
            <div style={{ fontWeight: 700 }}>{user?.email}</div>
            <div style={{ color: "#475569", fontSize: 12 }}>{user?.roles.join(", ")}</div>
          </div>
          <button onClick={handleLogout} style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #cbd5e1" }}>
            Выход
          </button>
        </header>
        <div style={{ padding: "24px" }}>
          <Outlet />
        </div>
      </main>
    </div>
  );
};

export default Layout;
