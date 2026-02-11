import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
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
import { isDemoClient } from "@shared/demo/demo";
import "./client-layout.css";

const MODE_STORAGE_KEY = "neft.client.mode";

export type ClientMode = "personal" | "fleet";

export type ClientNavItem = {
  to: string;
  label: string;
  shortLabel?: string;
  icon: ReactNode;
  audience: "all" | "fleet";
};

const getInitialMode = (): ClientMode => {
  const saved = localStorage.getItem(MODE_STORAGE_KEY);
  if (saved === "fleet" || saved === "personal") {
    return saved;
  }
  return "personal";
};

const navItems: ClientNavItem[] = [
  {
    to: "/dashboard",
    label: "Обзор",
    shortLabel: "Обзор",
    icon: <LayoutDashboard size={18} />,
    audience: "all",
  },
  {
    to: "/vehicles",
    label: "Автомобили",
    shortLabel: "Авто",
    icon: <Package size={18} />,
    audience: "all",
  },
  {
    to: "/cards",
    label: "Топливо и карты",
    shortLabel: "Топливо",
    icon: <ShoppingCart size={18} />,
    audience: "all",
  },
  {
    to: "/spend/transactions",
    label: "Расходы",
    shortLabel: "Расходы",
    icon: <FileSpreadsheet size={18} />,
    audience: "all",
  },
  {
    to: "/analytics",
    label: "Аналитика",
    shortLabel: "Аналитика",
    icon: <LineChart size={18} />,
    audience: "all",
  },
  {
    to: "/documents",
    label: "Документы",
    shortLabel: "Док",
    icon: <FileText size={18} />,
    audience: "all",
  },
  {
    to: "/client/support",
    label: "Поддержка",
    shortLabel: "Поддержка",
    icon: <MessageCircle size={18} />,
    audience: "all",
  },
  {
    to: "/settings",
    label: "Настройки",
    shortLabel: "Настройки",
    icon: <Settings size={18} />,
    audience: "all",
  },
  {
    to: "/fleet/groups",
    label: "Автопарк",
    shortLabel: "Автопарк",
    icon: <Package size={18} />,
    audience: "fleet",
  },
  {
    to: "/logistics/fleet",
    label: "Логистика · Автопарк",
    shortLabel: "Логистика",
    icon: <Package size={18} />,
    audience: "fleet",
  },
  {
    to: "/logistics/trips",
    label: "Логистика · Рейсы",
    shortLabel: "Рейсы",
    icon: <Package size={18} />,
    audience: "fleet",
  },
  {
    to: "/logistics/fuel-control",
    label: "Логистика · Топливо",
    shortLabel: "Топливо",
    icon: <Package size={18} />,
    audience: "fleet",
  },
  {
    to: "/fleet/employees",
    label: "Пользователи",
    shortLabel: "Люди",
    icon: <Workflow size={18} />,
    audience: "fleet",
  },
  {
    to: "/limits/templates",
    label: "Лимиты",
    shortLabel: "Лимиты",
    icon: <ClipboardCheck size={18} />,
    audience: "fleet",
  },
  {
    to: "/client/reports",
    label: "Отчёты",
    shortLabel: "Отчёты",
    icon: <FileSpreadsheet size={18} />,
    audience: "fleet",
  },
];

interface ClientLayoutProps {
  pwaMode?: boolean;
}

export function ClientLayout({ pwaMode = isPwaMode }: ClientLayoutProps) {
  const { user, logout } = useAuth();
  const { isFeatureDisabled } = useLegalGate();
  const location = useLocation();
  const [theme, setTheme] = useState(getInitialTheme());
  const [mode, setMode] = useState<ClientMode>(getInitialMode());
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const isDemoAccount = isDemoClient(user?.email ?? null);

  useEffect(() => {
    localStorage.setItem(MODE_STORAGE_KEY, mode);
    window.dispatchEvent(new CustomEvent("neftc:client-mode", { detail: mode }));
  }, [mode]);

  const filteredItems = useMemo(
    () => navItems.filter((item) => item.audience === "all" || mode === "fleet"),
    [mode],
  );

  const activePath = location.pathname;

  const bottomNavItems = filteredItems.filter((item) =>
    ["/dashboard", "/vehicles", "/cards", "/spend/transactions"].includes(item.to),
  );
  const bottomNavExtraItems = filteredItems.filter((item) => !bottomNavItems.includes(item));

  return (
    <div className={`neftc-app neftc-layout ${isSidebarCollapsed ? "neftc-layout--collapsed" : ""}`}>
      <ClientSidebar items={filteredItems} activePath={activePath} isCollapsed={isSidebarCollapsed} />
      <div className="neftc-main">
        <ClientTopbar
          title="Клиентский портал"
          activePath={activePath}
          items={filteredItems}
          userEmail={user?.email}
          mode={mode}
          onToggleMode={() => setMode((prev) => (prev === "fleet" ? "personal" : "fleet"))}
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
