import type { ReactNode } from "react";
import { AppLogo } from "./AppLogo";

export type BrandHeaderProps = {
  title?: ReactNode;
  subtitle?: ReactNode;
  meta?: ReactNode;
  userSlot?: ReactNode;
};

export function BrandHeader({ title, subtitle, meta, userSlot }: BrandHeaderProps) {
  return (
    <header className="brand-header">
      <div className="brand-header__meta">
        <AppLogo size={32} className="brand-logo" tone="white" />
        <div className="brand-header__titles">
          <div className="brand-header__eyebrow">NEFT platform</div>
          <div className="brand-header__title">{title}</div>
          {subtitle ? <div className="brand-header__subtitle">{subtitle}</div> : null}
        </div>
        {meta ? <div className="brand-header__tag">{meta}</div> : null}
      </div>
      {userSlot ? <div className="brand-header__user">{userSlot}</div> : null}
    </header>
  );
}

export default BrandHeader;
