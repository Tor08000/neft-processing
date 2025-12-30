import { NavLink, Outlet } from "react-router-dom";
import {
  BadgeDollarSign,
  FileText,
  Fuel,
  LayoutDashboard,
  LinkIcon,
  MessageCircle,
  Package,
  Settings,
  ShieldCheck,
  Wrench,
  Wallet,
  Workflow,
} from "./icons";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";

export function Layout() {
  const { user, logout } = useAuth();
  const { t } = useI18n();

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar__meta">
          <span className="logo">NEFT</span>
          <div className="topbar__title">{t("app.title")}</div>
          <div className="muted">
            {user?.partnerId ? t("app.partnerLabel", { id: user.partnerId }) : t("app.partnerFallback")}
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
          <NavLink to="/" end>
            <LayoutDashboard size={18} />
            {t("nav.dashboard")}
          </NavLink>
          <NavLink to="/stations">
            <Fuel size={18} />
            {t("nav.stations")}
          </NavLink>
          <NavLink to="/prices">
            <BadgeDollarSign size={18} />
            {t("nav.prices")}
          </NavLink>
          <NavLink to="/transactions">
            <Workflow size={18} />
            {t("nav.transactions")}
          </NavLink>
          <NavLink to="/orders">
            <Package size={18} />
            {t("nav.orders")}
          </NavLink>
          <NavLink to="/refunds">
            <ShieldCheck size={18} />
            {t("nav.refunds")}
          </NavLink>
          <NavLink to="/payouts">
            <Wallet size={18} />
            {t("nav.payouts")}
          </NavLink>
          <NavLink to="/documents">
            <FileText size={18} />
            {t("nav.documents")}
          </NavLink>
          <NavLink to="/services">
            <Wrench size={18} />
            {t("nav.services")}
          </NavLink>
          <NavLink to="/integrations">
            <LinkIcon size={18} />
            {t("nav.integrations")}
          </NavLink>
          <NavLink to="/support/requests">
            <MessageCircle size={18} />
            {t("nav.supportRequests")}
          </NavLink>
          <NavLink to="/settings">
            <Settings size={18} />
            {t("nav.settings")}
          </NavLink>
        </nav>

        <main className="main-area">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
