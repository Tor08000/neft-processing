import { useEffect, useState, type ReactNode } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import {
  Bell,
  MessageCircle,
  Package,
  ShoppingCart,
  FileSpreadsheet,
  LineChart,
} from "./icons";
import { useAuth } from "../auth/AuthContext";
import { useClient } from "../auth/ClientContext";
import { useLegalGate } from "../auth/LegalGateContext";
import { API_BASE_URL, CLIENT_BASE_PATH } from "../api/base";
import { getClientNotificationsUnreadCount } from "../api/clientNotifications";
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
  module?: string;
  capability?: string;
  requiredRole?: boolean;
  disabledReason?: string | null;
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
  const { isBlocked, isFeatureDisabled } = useLegalGate();
  const { t } = useI18n();
  const location = useLocation();
  const [theme, setTheme] = useState(getInitialTheme());
  const [unreadCount, setUnreadCount] = useState<number | null>(null);
  const isApiBaseMissing = !API_BASE_URL;
  const configError = !CLIENT_BASE_PATH ? t("app.configMissing") : null;

  const modulesPayload = client?.entitlements_snapshot?.modules as Record<string, { enabled?: boolean }> | undefined;
  const enabledModules = new Set(
    Object.entries(modulesPayload ?? {})
      .filter(([, payload]) => payload?.enabled)
      .map(([code]) => code.toUpperCase()),
  );
  const capabilities = new Set((client?.capabilities ?? []).map((code) => code.toUpperCase()));
  const isModuleEnabled = (module?: string) => (module ? enabledModules.has(module) : true);
  const hasCapability = (capability?: string) => (capability ? capabilities.has(capability) : true);
  const canSeeReports = hasAnyRole(user, [
    "CLIENT_OWNER",
    "CLIENT_ADMIN",
    "CLIENT_ACCOUNTANT",
    "CLIENT_FLEET_MANAGER",
  ]);
  const canSeeSlo = hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ADMIN"]);
  const canSeeAnalytics = hasAnyRole(user, [
    "CLIENT_OWNER",
    "CLIENT_ADMIN",
    "CLIENT_ACCOUNTANT",
    "CLIENT_FLEET_MANAGER",
  ]);

  const navItems: NavItem[] = [
    { to: "/vehicles", label: "Vehicles", icon: <Package size={18} />, module: "FLEET", capability: "CLIENT_CORE" },
    { to: "/cards", label: "Cards", icon: <Package size={18} />, capability: "CLIENT_CORE" },
    { to: "/limits/templates", label: "Limit Templates", icon: <Package size={18} />, capability: "CLIENT_CORE" },
    { to: "/orders", label: "Orders", icon: <ShoppingCart size={18} />, module: "MARKETPLACE", capability: "MARKETPLACE" },
    { to: "/billing", label: "Billing", icon: <ShoppingCart size={18} />, module: "DOCS", capability: "CLIENT_BILLING" },
    { to: "/client/notifications", label: "Notifications", icon: <Bell size={18} />, capability: "CLIENT_CORE" },
    { to: "/client/support", label: "Support", icon: <MessageCircle size={18} />, capability: "CLIENT_CORE" },
    { to: "/audit", label: "Audit", icon: <MessageCircle size={18} />, capability: "CLIENT_CORE" },
    {
      to: "/client/analytics",
      label: "Analytics",
      icon: <LineChart size={18} />,
      requiredRole: canSeeAnalytics,
      module: "ANALYTICS",
      capability: "CLIENT_ANALYTICS",
    },
    { to: "/client/reports", label: "Reports", icon: <FileSpreadsheet size={18} />, requiredRole: canSeeReports, capability: "CLIENT_CORE" },
    { to: "/client/exports", label: "Exports", icon: <FileSpreadsheet size={18} />, requiredRole: canSeeReports, capability: "CLIENT_CORE" },
    { to: "/client/slo", label: "SLO / SLA", icon: <LineChart size={18} />, requiredRole: canSeeSlo, capability: "CLIENT_CORE" },
    { to: "/marketplace", label: "Marketplace", icon: <ShoppingCart size={18} />, module: "MARKETPLACE", capability: "MARKETPLACE" },
    { to: "/legal", label: "Legal" },
  ].map((item) => {
    const lacksModule = item.module && !isModuleEnabled(item.module);
    const lacksCapability = item.capability && !hasCapability(item.capability);
    const lacksRole = item.requiredRole === false;
    const disabledReason = lacksRole
      ? "Нужна роль"
      : lacksModule || lacksCapability
        ? "Недоступно по подписке"
        : null;
    if (disabledReason) {
      return { ...item, disabledReason };
    }
    return item;
  });

  const visibleNavItems = isBlocked ? navItems.filter((item) => item.to === "/legal") : navItems;
  const sidebarItems = visibleNavItems.map((item) => ({
    ...item,
    disabled: Boolean(item.disabledReason),
    hint: item.disabledReason ?? undefined,
  }));

  const activeItem = visibleNavItems.find(
    (item) => location.pathname === item.to || location.pathname.startsWith(`${item.to}/`),
  );
  const sectionTitle = activeItem?.label ?? t("app.title");
  const contextLabel = buildContextLabel(sectionTitle, location.pathname, activeItem?.to);

  useEffect(() => {
    if (!user) {
      setUnreadCount(null);
      return;
    }
    let mounted = true;
    const fetchUnread = async () => {
      try {
        const response = await getClientNotificationsUnreadCount(user);
        if (mounted) {
          setUnreadCount(response.count);
        }
      } catch {
        if (mounted) {
          setUnreadCount(null);
        }
      }
    };
    void fetchUnread();
    const timer = window.setInterval(fetchUnread, 10000);
    return () => {
      mounted = false;
      window.clearInterval(timer);
    };
  }, [user]);

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
    <div className="brand-shell neftc-app">
      <BrandSidebar items={sidebarItems} title="Client" />
      <main className="brand-main">
        <BrandHeader
          title={sectionTitle}
          subtitle={contextLabel}
          meta={user?.clientId ? t("app.clientLabel", { id: user.clientId }) : t("app.clientFallback")}
          userSlot={
            <>
              <Link to="/client/notifications" className="notification-bell" aria-label="Notifications">
                <Bell size={18} />
                {unreadCount && unreadCount > 0 ? (
                  <span className="notification-bell__badge">{unreadCount}</span>
                ) : null}
              </Link>
              <div>
                <div className="muted">{t("app.signedInAs")}</div>
                <strong>{user?.email}</strong>
                <div className="roles">{user?.roles.join(", ")}</div>
              </div>
              <button type="button" className="neftc-btn-primary" onClick={() => setTheme(toggleTheme(theme))}>
                Theme: {theme}
              </button>
              <button className="ghost neft-btn-secondary" onClick={logout} type="button">
                {t("actions.logout")}
              </button>
            </>
          }
        />
        <div className="brand-content">
          {isFeatureDisabled ? (
            <div className="card">
              <div className="muted">Онбординг выключен администратором.</div>
            </div>
          ) : null}
          {pwaMode ? <PwaNotificationsPrompt /> : null}
          <PageShell key={location.pathname}>
            <Outlet />
          </PageShell>
        </div>
      </main>
    </div>
  );
}
