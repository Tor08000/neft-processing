import { Link } from "react-router-dom";
import type { ClientNavItem } from "./ClientLayout";

interface ClientSidebarProps {
  items: ClientNavItem[];
  activePath: string;
  isCollapsed: boolean;
}

const isActive = (path: string, target: string) =>
  path === target || (target !== "/" && path.startsWith(`${target}/`));

export function ClientSidebar({ items, activePath, isCollapsed }: ClientSidebarProps) {
  return (
    <aside className={`neftc-sidebar ${isCollapsed ? "neftc-sidebar--collapsed" : ""}`}>
      <div className="neftc-sidebar__brand">
        <div className="neftc-sidebar__logo">NEFT</div>
        <div className="neftc-sidebar__subtitle">Клиентский кабинет</div>
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
