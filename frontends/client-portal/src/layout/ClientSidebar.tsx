import { Link } from "react-router-dom";
import { AppLogo } from "@shared/brand/components";
import type { ClientNavItem } from "./ClientLayout";

interface ClientSidebarProps {
  items: ClientNavItem[];
  activePath: string;
  isCollapsed: boolean;
}

const isSupportCaseTrail = (path: string) =>
  path === "/cases" ||
  path.startsWith("/cases/") ||
  path === "/support/requests" ||
  path.startsWith("/support/requests/");

const isActive = (path: string, target: string) =>
  path === target ||
  (target !== "/" && path.startsWith(`${target}/`)) ||
  (target === "/client/support" && isSupportCaseTrail(path));

export function ClientSidebar({ items, activePath, isCollapsed }: ClientSidebarProps) {
  return (
    <aside className={`neftc-sidebar ${isCollapsed ? "neftc-sidebar--collapsed" : ""}`}>
      <div className="neftc-sidebar__brand">
        <AppLogo
          variant={isCollapsed ? "mark" : "full"}
          size={30}
          tone="white"
          className="neftc-sidebar__logo"
        />
        {!isCollapsed ? (
          <div className="neftc-sidebar__brand-copy">
            <div className="neftc-sidebar__eyebrow">Client portal</div>
            <div className="neftc-sidebar__subtitle">onboarding-first service</div>
          </div>
        ) : null}
      </div>
      <nav className="neftc-sidebar__nav">
        {items.map((item) => {
          const active = isActive(activePath, item.to);
          return (
            <Link
              key={item.to}
              to={item.to}
              className={`neftc-nav-item ${active ? "neftc-nav-item--active" : ""}`}
            >
              <span className="neftc-nav-item__icon">{item.icon}</span>
              <span className="neftc-nav-item__label">{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
