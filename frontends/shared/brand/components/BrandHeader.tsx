import React from "react";
import { AppLogo } from "./AppLogo";

export type BrandHeaderProps = {
  title: string;
  subtitle?: string;
  meta?: React.ReactNode;
  userSlot?: React.ReactNode;
};

export const BrandHeader: React.FC<BrandHeaderProps> = ({ title, subtitle, meta, userSlot }) => {
  return (
    <header className="brand-header">
      <div className="brand-header__meta">
        <AppLogo size={32} className="brand-logo" />
        <div className="brand-header__titles">
          <div className="brand-header__title">{title}</div>
          {subtitle ? <div className="brand-header__subtitle">{subtitle}</div> : null}
        </div>
        {meta ? <div className="brand-header__tag">{meta}</div> : null}
      </div>
      {userSlot ? <div className="brand-header__user">{userSlot}</div> : null}
    </header>
  );
};

export default BrandHeader;
