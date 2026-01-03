import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { AppLogo } from "./AppLogo";

export type BrandNavItem = {
  to: string;
  label: string;
  icon?: ReactNode;
  end?: boolean;
};

export type BrandSidebarProps = {
  title?: string;
  items: BrandNavItem[];
  footerSlot?: ReactNode;
};

type NavLinkClassNameState = {
  isActive: boolean;
};

const navLinkClassName = ({ isActive }: NavLinkClassNameState) =>
  `brand-nav-link${isActive ? " is-active" : ""}`;

export function BrandSidebar({ title = "NEFT", items, footerSlot }: BrandSidebarProps) {
  return (
    <aside className="brand-sidebar">
      <div className="brand-sidebar__title" aria-label="NEFT Platform">
        <AppLogo size={28} className="brand-sidebar__logo" />
        <span>{title}</span>
      </div>
      <nav className="brand-sidebar__nav">
        {items.map((item: BrandNavItem) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={navLinkClassName}
          >
            {item.icon ? <span className="brand-nav-link__icon">{item.icon}</span> : null}
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>
      {footerSlot ? <div className="brand-sidebar__footer">{footerSlot}</div> : null}
    </aside>
  );
}

export default BrandSidebar;
