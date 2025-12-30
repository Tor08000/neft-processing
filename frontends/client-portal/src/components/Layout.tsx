import { NavLink, Outlet } from "react-router-dom";
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

export function Layout({ pwaMode = isPwaMode }: LayoutProps) {
  const { user, logout } = useAuth();
  const { t } = useI18n();
  const apiBase = CLIENT_BASE_PATH ? null : t("app.configMissing");
  const isApiBaseMissing = !import.meta.env.VITE_API_BASE && !import.meta.env.VITE_API_BASE_URL;
  const configError = isApiBaseMissing ? t("app.configError") : apiBase;

  if (configError) {
    return (
      <div className="app-shell">
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
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar__meta">
          <span className="logo">NEFT</span>
          <div className="topbar__title">{t("app.title")}</div>
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
          <button className="ghost" onClick={logout} type="button">
            {t("actions.logout")}
          </button>
        </div>
      </header>

      <div className="sidebar-layout">
        <nav className="sidebar">
          {pwaMode ? (
            <>
              <NavLink to="/marketplace/orders">
                <ShoppingCart size={18} />
                {t("nav.orders")}
              </NavLink>
              <NavLink to="/documents">
                <FileText size={18} />
                {t("nav.documents")}
              </NavLink>
            </>
          ) : (
            <>
              <NavLink to="/dashboard">
                <LayoutDashboard size={18} />
                {t("nav.dashboard")}
              </NavLink>
              {(hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_FLEET_MANAGER"]) || !user) && (
                <NavLink to="/operations">
                  <Workflow size={18} />
                  {t("nav.operations")}
                </NavLink>
              )}
              <NavLink to="/explain/insights">
                <LineChart size={18} />
                {t("nav.explainInsights")}
              </NavLink>
              <NavLink to="/documents">
                <FileText size={18} />
                {t("nav.documents")}
              </NavLink>
              {(hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ACCOUNTANT"]) || !user) && (
                <NavLink to="/exports">
                  <FileSpreadsheet size={18} />
                  {t("nav.exports")}
                </NavLink>
              )}
              <NavLink to="/marketplace">
                <ShoppingCart size={18} />
                {t("nav.marketplace")}
              </NavLink>
              <NavLink to="/actions">
                <ClipboardCheck size={18} />
                {t("nav.actions")}
              </NavLink>
              <NavLink to="/support/requests">
                <MessageCircle size={18} />
                {t("nav.supportRequests")}
              </NavLink>
              <NavLink to="/settings">
                <Settings size={18} />
                {t("nav.settings")}
              </NavLink>
              <NavLink to="/settings/management">
                <Settings size={18} />
                {t("nav.management")}
              </NavLink>
            </>
          )}
        </nav>

        <main className="main-area">
          {pwaMode ? <PwaNotificationsPrompt /> : null}
          <Outlet />
        </main>
      </div>
    </div>
  );
}
