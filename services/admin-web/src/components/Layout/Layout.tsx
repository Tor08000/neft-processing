import React from "react";
import { Link, useLocation } from "react-router-dom";

const navItems = [
  { to: "/", label: "Dashboard" },
  { to: "/operations", label: "Operations" },
  { to: "/billing", label: "Billing" },
  { to: "/clearing", label: "Clearing" },
  { to: "/health", label: "Health" },
];

export const Layout: React.FC<React.PropsWithChildren> = ({ children }) => {
  const location = useLocation();

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <aside
        style={{
          width: 220,
          background: "#0f172a",
          color: "#e2e8f0",
          padding: "20px 16px",
        }}
      >
        <div style={{ fontWeight: 800, fontSize: 18, marginBottom: 24 }}>NEFT Admin</div>
        <nav style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {navItems.map((item) => {
            const isActive =
              item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to);
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
      <main style={{ flex: 1, padding: "24px", background: "#f8fafc" }}>{children}</main>
    </div>
  );
};
