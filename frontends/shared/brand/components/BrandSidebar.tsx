import type { ReactNode } from "react";
import { NavLink, type NavLinkProps } from "react-router-dom";
import { AppLogo } from "./AppLogo";

export type BrandNavItem = {
  to: string;
  label: string;
  icon?: ReactNode;
  end?: boolean;
  disabled?: boolean;
  hint?: string;
};

export type BrandSidebarProps = {
  title?: string;
  items: BrandNavItem[];
  footerSlot?: ReactNode;
};

type NavLinkClassNameState = {
  isActive?: boolean;
};

const navLinkClassName: NavLinkProps["className"] = ({ isActive = false }: NavLinkClassNameState) =>
  `brand-nav-link${isActive ? " is-active" : ""}`;

export function BrandSidebar({ title = "NEFT", items, footerSlot }: BrandSidebarProps) {
  return (
    <aside className="brand-sidebar">
      <div className="brand-sidebar__title" aria-label="NEFT Platform">
        <AppLogo size={28} className="brand-sidebar__logo" />
        <span>{title}</span>
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
            <NavLink key={item.to} to={item.to} end={item.end} className={navLinkClassName}>
              {item.icon ? <span className="brand-nav-link__icon">{item.icon}</span> : null}
              <span className="brand-nav-link__label">{item.label}</span>
            </NavLink>
          ),
        )}
      </nav>
      {footerSlot ? <div className="brand-sidebar__footer">{footerSlot}</div> : null}
    </aside>
  );
}

export default BrandSidebar;
