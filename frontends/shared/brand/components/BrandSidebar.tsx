import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { AppLogo } from "./AppLogo";

export type BrandNavItem = {
  to: string;
  label: string;
  icon?: ReactNode;
  end?: boolean;
  disabled?: boolean;
  hint?: string;
  matchPaths?: string[];
};

export type BrandSidebarProps = {
  title?: string;
  items: BrandNavItem[];
  footerSlot?: ReactNode;
};

const matchesPathPrefix = (pathname: string, prefix: string) =>
  pathname === prefix || pathname.startsWith(`${prefix}/`);

const isItemActive = (item: BrandNavItem, pathname: string) => {
  const matchesPrimary = item.end ? pathname === item.to : matchesPathPrefix(pathname, item.to);
  if (matchesPrimary) {
    return true;
  }
  return (item.matchPaths ?? []).some((prefix) => matchesPathPrefix(pathname, prefix));
};

export function BrandSidebar({ title = "NEFT", items, footerSlot }: BrandSidebarProps) {
  const location = useLocation();

  return (
    <aside className="brand-sidebar">
      <div className="brand-sidebar__title" aria-label="NEFT Platform">
        <AppLogo variant="full" size={30} className="brand-sidebar__logo" tone="white" />
        <div className="brand-sidebar__title-copy">
          <span className="brand-sidebar__eyebrow">{title}</span>
          <span className="brand-sidebar__caption">operator surface</span>
        </div>
      </div>
      <nav className="brand-sidebar__nav">
        {items.map((item: BrandNavItem) =>
          item.disabled ? (
            <span key={item.to} className="brand-nav-link is-disabled" aria-disabled="true">
              {item.icon ? <span className="brand-nav-link__icon">{item.icon}</span> : null}
              <span className="brand-nav-link__label">{item.label}</span>
              {item.hint ? <span className="brand-nav-link__hint">{item.hint}</span> : null}
            </span>
          ) : (
            <Link
              key={item.to}
              to={item.to}
              className={`brand-nav-link${isItemActive(item, location.pathname) ? " is-active" : ""}`}
              aria-current={isItemActive(item, location.pathname) ? "page" : undefined}
            >
              {item.icon ? <span className="brand-nav-link__icon">{item.icon}</span> : null}
              <span className="brand-nav-link__label">{item.label}</span>
              {item.hint ? <span className="brand-nav-link__hint">{item.hint}</span> : null}
            </Link>
          ),
        )}
      </nav>
      {footerSlot ? <div className="brand-sidebar__footer">{footerSlot}</div> : null}
    </aside>
  );
}

export default BrandSidebar;
