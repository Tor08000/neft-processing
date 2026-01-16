import { useState, type ReactNode } from "react";
import { Outlet, useLocation } from "react-router-dom";
import {
  MessageCircle,
  Package,
  ShoppingCart,
  FileSpreadsheet,
} from "./icons";
import { useAuth } from "../auth/AuthContext";
import { useClient } from "../auth/ClientContext";
import { useLegalGate } from "../auth/LegalGateContext";
import { API_BASE_URL, CLIENT_BASE_PATH } from "../api/base";
import { AppErrorState } from "./states";
import { useI18n } from "../i18n";
import { isPwaMode } from "../pwa/mode";
import { PwaNotificationsPrompt } from "../pwa/PwaNotificationsPrompt";
import { BrandHeader, BrandSidebar, PageShell } from "@shared/brand/components";
import { getInitialTheme, toggleTheme } from "../lib/theme";
import { hasAnyRole } from "../utils/roles";

interface LayoutProps {
  pwaMode?: boolean;
}

type NavItem = {
  to: string;
  label: string;
  icon?: ReactNode;
  isHidden?: boolean;
  module?: string;
};

const buildContextLabel = (section: string, path: string, basePath?: string) => {
  if (!basePath) return "Обзор";
  const suffix = path.replace(basePath, "");
  const trail = suffix
    .split("/")
    .filter(Boolean)
    .map((segment) => decodeURIComponent(segment));
  return trail.length ? `${section} → ${trail.join(" / ")}` : `${section} → Обзор`;
};

export function Layout({ pwaMode = isPwaMode }: LayoutProps) {
  const { user, logout } = useAuth();
  const { client } = useClient();
  const { isBlocked } = useLegalGate();
  const { t } = useI18n();
  const location = useLocation();
  const [theme, setTheme] = useState(getInitialTheme());
  const isApiBaseMissing = !API_BASE_URL;
  const configError = !CLIENT_BASE_PATH ? t("app.configMissing") : null;

  const enabledModules = new Set((client?.entitlements.enabled_modules ?? []).map((code) => code.toUpperCase()));
  const isModuleEnabled = (module?: string) => (module ? enabledModules.has(module) : true);
  const canSeeReports = hasAnyRole(user, [
    "CLIENT_OWNER",
    "CLIENT_ADMIN",
    "CLIENT_ACCOUNTANT",
    "CLIENT_FLEET_MANAGER",
  ]);

  const navItems: NavItem[] = [
    { to: "/vehicles", label: "Vehicles", icon: <Package size={18} />, module: "FLEET" },
    { to: "/cards", label: "Cards", icon: <Package size={18} /> },
    { to: "/limits/templates", label: "Limit Templates", icon: <Package size={18} /> },
    { to: "/orders", label: "Orders", icon: <ShoppingCart size={18} />, module: "MARKETPLACE" },
    { to: "/billing", label: "Billing", icon: <ShoppingCart size={18} />, module: "DOCS" },
    { to: "/client/support", label: "Support", icon: <MessageCircle size={18} /> },
    { to: "/audit", label: "Audit", icon: <MessageCircle size={18} /> },
    { to: "/client/reports", label: "Reports", icon: <FileSpreadsheet size={18} />, isHidden: !canSeeReports },
    { to: "/client/exports", label: "Exports", icon: <FileSpreadsheet size={18} />, isHidden: !canSeeReports },
    { to: "/marketplace", label: "Marketplace", icon: <ShoppingCart size={18} />, module: "MARKETPLACE" },
    { to: "/legal", label: "Legal" },
  ].map((item) => {
    if (!isModuleEnabled(item.module)) {
      return { ...item, label: `${item.label} · Недоступно` };
    }
    return item;
  });

  const visibleNavItems = (isBlocked ? navItems.filter((item) => item.to === "/legal") : navItems).filter(
    (item) => !item.isHidden,
  );
  const activeItem = visibleNavItems.find(
    (item) => location.pathname === item.to || location.pathname.startsWith(`${item.to}/`),
  );
  const sectionTitle = activeItem?.label ?? t("app.title");
  const contextLabel = buildContextLabel(sectionTitle, location.pathname, activeItem?.to);

  if (isApiBaseMissing) {
    return (
      <div className="brand-shell neft-page neft-app">
        <main className="brand-main">
          <BrandHeader title={t("app.title")} />
          <div className="card state">
            <h2>{t("app.configMissingTitle")}</h2>
            <div className="muted">{t("app.configMissingDescription")}</div>
            <pre className="code-sample">{t("app.configMissingExample")}</pre>
          </div>
        </main>
      </div>
    );
  }

  if (configError) {
    return (
      <div className="brand-shell neft-page neft-app">
        <main className="brand-main">
          <BrandHeader title={t("app.title")} />
          <AppErrorState message={configError} />
        </main>
      </div>
    );
  }

  return (
    <div className="brand-shell neft-page neft-app">
      <BrandSidebar items={visibleNavItems} title="Client" />
      <main className="brand-main">
        <BrandHeader
          title={sectionTitle}
          subtitle={contextLabel}
          meta={user?.clientId ? t("app.clientLabel", { id: user.clientId }) : t("app.clientFallback")}
          userSlot={
            <>
              <div>
                <div className="muted">{t("app.signedInAs")}</div>
            <strong>{user?.email}</strong>
            <div className="roles">{user?.roles.join(", ")}</div>
          </div>
          <button type="button" className="neft-btn neft-btn-outline" onClick={() => setTheme(toggleTheme(theme))}>
            Theme: {theme}
          </button>
          <button className="ghost neft-btn-secondary" onClick={logout} type="button">
            {t("actions.logout")}
          </button>
            </>
          }
        />
        <div className="brand-content">
          {pwaMode ? <PwaNotificationsPrompt /> : null}
          <PageShell key={location.pathname}>
            <Outlet />
          </PageShell>
        </div>
      </main>
    </div>
  );
}
