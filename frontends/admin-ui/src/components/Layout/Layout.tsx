import React, { useState } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { useLegalGate } from "../../auth/LegalGateContext";
import { BrandHeader, BrandSidebar, PageShell } from "@shared/brand/components";
import { getInitialTheme, toggleTheme } from "../../lib/theme";

const baseNavItems = [
  { to: "/operations", label: "Ops" },
  { to: "/finance", label: "Finance" },
  { to: "/finance/revenue", label: "Revenue" },
  { to: "/stubs", label: "Stubs" },
  { to: "/risk", label: "Risk" },
  { to: "/risk/sandbox", label: "Rules Sandbox" },
  { to: "/policies", label: "Policies" },
  { to: "/marketplace", label: "Marketplace" },
  { to: "/users", label: "Users" },
  { to: "/legal", label: "Legal" },
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
  const { isBlocked } = useLegalGate();
  const [theme, setTheme] = useState(getInitialTheme());

  const navItems = isBlocked ? baseNavItems.filter((item) => item.to === "/legal") : baseNavItems;

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
    <div className="brand-shell neft-page neft-app">
      <BrandSidebar
        items={navItems.map((item) => ({
          ...item,
          icon: <span aria-hidden>◆</span>,
        }))}
        title="Admin"
      />
      <main className="brand-main">
        <BrandHeader
          title={sectionTitle}
          subtitle={contextLabel}
          userSlot={
            <>
              <div>
                <div className="admin-user__email">{user?.email}</div>
                <div className="admin-user__roles">{user?.roles.join(", ")}</div>
              </div>
              <button
                type="button"
                className="neft-btn neft-btn-outline"
                onClick={() => setTheme(toggleTheme(theme))}
              >
                Theme: {theme}
              </button>
              <button onClick={handleLogout} className="neft-btn-secondary" type="button">
                Выход
              </button>
            </>
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

export default Layout;
