import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import type { ClientNavItem } from "./ClientLayout";

interface ClientBottomNavProps {
  items: ClientNavItem[];
  extraItems: ClientNavItem[];
  activePath: string;
}

const isActive = (path: string, target: string) =>
  path === target || (target !== "/" && path.startsWith(`${target}/`));

export function ClientBottomNav({ items, extraItems, activePath }: ClientBottomNavProps) {
  const [isMoreOpen, setIsMoreOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setIsMoreOpen(false);
  }, [location.pathname]);

  return (
    <div className="neftc-bottomnav">
      <div className="neftc-bottomnav__bar">
        {items.map((item) => {
          const active = isActive(activePath, item.to);
          return (
            <Link
              key={item.to}
              to={item.to}
              className={`neftc-bottomnav__item ${active ? "neftc-bottomnav__item--active" : ""}`}
            >
              <span className="neftc-bottomnav__icon">{item.icon}</span>
              <span className="neftc-bottomnav__label">{item.shortLabel ?? item.label}</span>
            </Link>
          );
        })}
        <button
          type="button"
          className={`neftc-bottomnav__item ${isMoreOpen ? "neftc-bottomnav__item--active" : ""}`}
          onClick={() => setIsMoreOpen((prev) => !prev)}
        >
          <span className="neftc-bottomnav__icon">⋯</span>
          <span className="neftc-bottomnav__label">Ещё</span>
        </button>
      </div>
      <div className={`neftc-bottomnav__drawer ${isMoreOpen ? "is-open" : ""}`}>
        <div className="neftc-bottomnav__drawer-head">
          Дополнительно
          <button type="button" className="neftc-link" onClick={() => setIsMoreOpen(false)}>
            Закрыть
          </button>
        </div>
        <div className="neftc-bottomnav__drawer-list">
          {extraItems.map((item) => (
            <Link key={item.to} to={item.to} className="neftc-bottomnav__drawer-item">
              <span className="neftc-bottomnav__icon">{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
