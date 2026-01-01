import { NavLink, Outlet, useLocation } from "react-router-dom";
import {
  ClipboardCheck,
  FileSpreadsheet,
  FileText,
  LayoutDashboard,
  LineChart,
  MessageCircle,
  Settings,
  ShoppingCart,
  Workflow,
} from "./icons";
import { useAuth } from "../auth/AuthContext";
import { CLIENT_BASE_PATH } from "../api/base";
import { hasAnyRole } from "../utils/roles";
import { AppErrorState } from "./states";
import { useI18n } from "../i18n";
import { isPwaMode } from "../pwa/mode";
import { PwaNotificationsPrompt } from "../pwa/PwaNotificationsPrompt";

interface LayoutProps {
  pwaMode?: boolean;
}

type NavItem = {
  to: string;
  label: string;
  icon?: React.ReactNode;
  isHidden?: boolean;
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
  const { t } = useI18n();
  const location = useLocation();
  const apiBase = CLIENT_BASE_PATH ? null : t("app.configMissing");
  const isApiBaseMissing = !import.meta.env.VITE_API_BASE && !import.meta.env.VITE_API_BASE_URL;
  const configError = isApiBaseMissing ? t("app.configError") : apiBase;

  const navItems: NavItem[] = pwaMode
    ? [
        { to: "/marketplace/orders", label: t("nav.orders"), icon: <ShoppingCart size={18} /> },
        { to: "/documents", label: t("nav.documents"), icon: <FileText size={18} /> },
      ]
    : [
        { to: "/dashboard", label: t("nav.dashboard"), icon: <LayoutDashboard size={18} /> },
        { to: "/analytics", label: t("nav.analytics"), icon: <LineChart size={18} /> },
        {
          to: "/operations",
          label: t("nav.operations"),
          icon: <Workflow size={18} />,
          isHidden: !(hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_FLEET_MANAGER"]) || !user),
        },
        { to: "/explain/insights", label: t("nav.explainInsights"), icon: <LineChart size={18} /> },
        { to: "/documents", label: t("nav.documents"), icon: <FileText size={18} /> },
        {
          to: "/exports",
          label: t("nav.exports"),
          icon: <FileSpreadsheet size={18} />,
          isHidden: !(hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ACCOUNTANT"]) || !user),
        },
        { to: "/marketplace", label: t("nav.marketplace"), icon: <ShoppingCart size={18} /> },
        { to: "/actions", label: t("nav.actions"), icon: <ClipboardCheck size={18} /> },
        { to: "/support/requests", label: t("nav.supportRequests"), icon: <MessageCircle size={18} /> },
        { to: "/cases", label: t("nav.cases"), icon: <MessageCircle size={18} /> },
        { to: "/settings", label: t("nav.settings"), icon: <Settings size={18} /> },
        { to: "/settings/management", label: t("nav.management"), icon: <Settings size={18} /> },
      ];

  const visibleNavItems = navItems.filter((item) => !item.isHidden);
  const activeItem = visibleNavItems.find(
    (item) => location.pathname === item.to || location.pathname.startsWith(`${item.to}/`),
  );
  const sectionTitle = activeItem?.label ?? t("app.title");
  const contextLabel = buildContextLabel(sectionTitle, location.pathname, activeItem?.to);

  if (configError) {
    return (
      <div className="app-shell neft-page">
        <header className="topbar">
          <div className="topbar__meta">
            <span className="logo">NEFT</span>
            <div className="topbar__title">{t("app.title")}</div>
          </div>
        </header>
        <main className="main-area">
          <AppErrorState message={configError} />
        </main>
      </div>
    );
  }

  return (
    <div className="app-shell neft-page">
      <header className="topbar">
        <div className="topbar__meta">
          <span className="logo">NEFT</span>
          <div className="topbar__titles">
            <div className="topbar__title">{sectionTitle}</div>
            <div className="topbar__context">{contextLabel}</div>
          </div>
          <div className="muted">
            {user?.clientId ? t("app.clientLabel", { id: user.clientId }) : t("app.clientFallback")}
          </div>
        </div>
        <div className="topbar__meta topbar__meta--user">
          <div>
            <div className="muted">{t("app.signedInAs")}</div>
            <strong>{user?.email}</strong>
            <div className="roles">{user?.roles.join(", ")}</div>
          </div>
          <button className="ghost neft-btn-secondary" onClick={logout} type="button">
            {t("actions.logout")}
          </button>
        </div>
      </header>

      <div className="sidebar-layout">
        <nav className="sidebar">
          {visibleNavItems.map((item) => (
            <NavLink key={item.to} to={item.to} title={item.label}>
              {item.icon}
              {item.label}
            </NavLink>
          ))}
        </nav>

        <main className="main-area">
          {pwaMode ? <PwaNotificationsPrompt /> : null}
          <Outlet />
        </main>
      </div>
    </div>
  );
}
