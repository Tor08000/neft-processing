import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useClient } from "../auth/ClientContext";
import { useClientJourney } from "../auth/ClientJourneyContext";
import { resolveAvailableClientModes, type ClientMode } from "../auth/clientModes";
import { resolveClientWorkspace } from "../access/clientWorkspace";
import { useLegalGate } from "../auth/LegalGateContext";
import { isPwaMode } from "../pwa/mode";
import { PwaNotificationsPrompt } from "../pwa/PwaNotificationsPrompt";
import { getInitialTheme, toggleTheme } from "../lib/theme";
import {
  FileSpreadsheet,
  FileText,
  LayoutDashboard,
  LineChart,
  MessageCircle,
  Package,
  Settings,
  ShoppingCart,
  Workflow,
  ClipboardCheck,
} from "../components/icons";
import { ClientSidebar } from "./ClientSidebar";
import { ClientTopbar } from "./ClientTopbar";
import { ClientBottomNav } from "./ClientBottomNav";
import { demoClientNavManifest } from "./demoClientNavManifest";
import { isDemoClient } from "@shared/demo/demo";
import "./client-layout.css";

const MODE_STORAGE_KEY = "neft.client.mode";
const FLEET_ONLY_PREFIXES = [
  "/cards",
  "/fleet",
  "/limits",
  "/analytics",
  "/client/reports",
  "/logistics/fleet",
  "/logistics/trips",
  "/logistics/fuel-control",
];

const getModeLandingRoute = (mode: ClientMode): string => (mode === "fleet" ? "/fleet/groups" : "/dashboard");

const isFleetOnlyPath = (pathname: string): boolean =>
  FLEET_ONLY_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));

export type ClientNavItem = {
  to: string;
  label: string;
  shortLabel?: string;
  icon: ReactNode;
  audience: "all" | "business" | "fleet";
  requiresActivation?: boolean;
};

const getRouteMode = (pathname: string, availableModes: ClientMode[]): ClientMode =>
  isFleetOnlyPath(pathname) && availableModes.includes("fleet") ? "fleet" : "personal";

const navItems: ClientNavItem[] = [
  { to: "/dashboard", label: "Главная", shortLabel: "Главная", icon: <LayoutDashboard size={18} />, audience: "all" },
  { to: "/marketplace", label: "Маркетплейс", shortLabel: "Маркет", icon: <ShoppingCart size={18} />, audience: "all", requiresActivation: true },
  { to: "/marketplace/orders", label: "Заказы", shortLabel: "Заказы", icon: <Package size={18} />, audience: "all", requiresActivation: true },
  { to: "/invoices", label: "Финансы", shortLabel: "Финансы", icon: <FileSpreadsheet size={18} />, audience: "all", requiresActivation: true },
  { to: "/client/documents", label: "Документы", shortLabel: "Док", icon: <FileText size={18} />, audience: "all" },
  { to: "/client/support", label: "Поддержка", shortLabel: "Поддержка", icon: <MessageCircle size={18} />, audience: "all" },
  { to: "/subscription", label: "Подписка", shortLabel: "Тариф", icon: <ClipboardCheck size={18} />, audience: "all" },
  { to: "/settings/management", label: "Команда", shortLabel: "Команда", icon: <Workflow size={18} />, audience: "business", requiresActivation: true },
  { to: "/cards", label: "Карты", shortLabel: "Карты", icon: <ShoppingCart size={18} />, audience: "fleet", requiresActivation: true },
  { to: "/fleet/groups", label: "Автопарк", shortLabel: "Автопарк", icon: <Package size={18} />, audience: "fleet", requiresActivation: true },
  { to: "/limits/templates", label: "Лимиты", shortLabel: "Лимиты", icon: <ClipboardCheck size={18} />, audience: "fleet", requiresActivation: true },
  { to: "/analytics", label: "Аналитика", shortLabel: "Аналитика", icon: <LineChart size={18} />, audience: "fleet", requiresActivation: true },
  { to: "/client/reports", label: "Отчёты", shortLabel: "Отчёты", icon: <FileSpreadsheet size={18} />, audience: "fleet", requiresActivation: true },
  { to: "/logistics/trips", label: "Логистика", shortLabel: "Логистика", icon: <Package size={18} />, audience: "fleet", requiresActivation: true },
  { to: "/profile", label: "Профиль", shortLabel: "Профиль", icon: <Workflow size={18} />, audience: "all" },
  { to: "/settings", label: "Настройки", shortLabel: "Настройки", icon: <Settings size={18} />, audience: "all" },
];

interface ClientLayoutProps {
  pwaMode?: boolean;
}

export function ClientLayout({ pwaMode = isPwaMode }: ClientLayoutProps) {
  const { user, logout } = useAuth();
  const { client } = useClient();
  const { state: journeyState } = useClientJourney();
  const { isFeatureDisabled } = useLegalGate();
  const location = useLocation();
  const navigate = useNavigate();
  const [theme, setTheme] = useState(getInitialTheme());
  const [mode, setMode] = useState<ClientMode>("personal");
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const isDemoAccount = isDemoClient(user?.email ?? null);
  const workspace = useMemo(() => resolveClientWorkspace({ client }), [client]);

  const availableModes = useMemo(
    () => resolveAvailableClientModes({ journeyState, client }),
    [journeyState, client],
  );

  const navigateToMode = (nextMode: ClientMode, replace = false) => {
    const nextRoute = getModeLandingRoute(nextMode);
    if (location.pathname !== nextRoute) {
      navigate(nextRoute, { replace });
    }
  };

  useEffect(() => {
    const wantsFleetRoute = isFleetOnlyPath(location.pathname);
    if (wantsFleetRoute && !availableModes.includes("fleet")) {
      if (mode !== "personal") {
        setMode("personal");
      }
      navigateToMode("personal", true);
      return;
    }

    const nextMode = getRouteMode(location.pathname, availableModes);
    if (nextMode !== mode) {
      setMode(nextMode);
    }
    localStorage.setItem(MODE_STORAGE_KEY, nextMode);
    window.dispatchEvent(new CustomEvent("neftc:client-mode", { detail: nextMode }));
  }, [availableModes, location.pathname, mode]);

  const hasActivatedClient = Boolean(client?.org?.id);

  const filteredItems = useMemo(() => {
    if (isDemoAccount) {
      // Demo accounts may keep an isolated navigation manifest, but live pages must still
      // surface honest backend empty/error states instead of switching to synthetic data.
      return demoClientNavManifest;
    }

    const activationAllowed = new Set(["/dashboard", "/client/documents", "/client/support", "/subscription", "/profile", "/settings"]);
    return navItems
      .filter((item) => {
        if (item.audience === "business" && workspace.clientKind !== "BUSINESS") {
          return false;
        }
        if (item.audience === "fleet" && !workspace.hasFleetWorkspace) {
          return false;
        }
        if (item.to === "/settings/management" && !workspace.hasTeamWorkspace) {
          return false;
        }
        if (item.to === "/analytics" && !workspace.hasAnalyticsWorkspace) {
          return false;
        }
        if ((item.to === "/marketplace" || item.to === "/marketplace/orders") && !workspace.hasMarketplaceWorkspace) {
          return false;
        }
        if (item.to === "/invoices" && !workspace.hasFinanceWorkspace) {
          return false;
        }
        if (item.to === "/client/documents" && !workspace.hasDocumentsWorkspace) {
          return false;
        }
        if (item.to === "/client/support" && !workspace.hasSupportWorkspace) {
          return false;
        }
        return !item.requiresActivation || hasActivatedClient || activationAllowed.has(item.to);
      });
  }, [hasActivatedClient, isDemoAccount, workspace]);

  const activePath = location.pathname;

  const bottomNavItems = filteredItems.filter((item) =>
    ["/dashboard", "/marketplace", "/invoices", "/client/documents"].includes(item.to),
  );
  const bottomNavExtraItems = filteredItems.filter((item) => !bottomNavItems.includes(item));

  return (
    <div className={`neftc-app neftc-layout ${isSidebarCollapsed ? "neftc-layout--collapsed" : ""}`}>
      <ClientSidebar items={filteredItems} activePath={activePath} isCollapsed={isSidebarCollapsed} />
      <div className="neftc-main">
        <ClientTopbar
          title={workspace.clientKind === "BUSINESS" ? "Кабинет компании" : "Личный кабинет"}
          activePath={activePath}
          items={filteredItems}
          userEmail={user?.email}
          mode={mode}
          theme={theme}
          onToggleTheme={() => setTheme(toggleTheme())}
          onToggleSidebar={() => setIsSidebarCollapsed((prev) => !prev)}
          onLogout={logout}
        />
        <div className="neftc-container">
          {isFeatureDisabled ? (
            <div className="neftc-card">
              <div className="neftc-text-muted">
                {isDemoAccount ? "Демо-режим: онбординг пропущен." : "Онбординг выключен администратором."}
              </div>
            </div>
          ) : null}
          {pwaMode ? <PwaNotificationsPrompt /> : null}
          <Outlet />
        </div>
      </div>
      <ClientBottomNav activePath={activePath} items={bottomNavItems} extraItems={bottomNavExtraItems} />
    </div>
  );
}
