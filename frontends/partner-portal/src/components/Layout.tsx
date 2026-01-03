import { Outlet, useLocation } from "react-router-dom";
import {
  BarChart3,
  Briefcase,
  Package,
  Percent,
  ShoppingBag,
  Wallet,
} from "./icons";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import { BrandHeader, BrandSidebar, PageShell } from "../../shared/brand/components";

export function Layout() {
  const { user, logout } = useAuth();
  const { t } = useI18n();
  const location = useLocation();

  const buildContextLabel = (section: string, path: string, basePath?: string) => {
    if (!basePath) return section;
    const suffix = path.replace(basePath, "");
    const trail = suffix
      .split("/")
      .filter(Boolean)
      .map((segment) => decodeURIComponent(segment));
    return trail.length ? `${section} → ${trail.join(" / ")}` : section;
  };

  const navItems = [
    { to: "/products", label: "Products", icon: <Package size={18} /> },
    { to: "/orders", label: "Orders", icon: <ShoppingBag size={18} /> },
    { to: "/bookings", label: "Bookings", icon: <Briefcase size={18} /> },
    { to: "/promotions", label: "Promotions", icon: <Percent size={18} /> },
    { to: "/analytics", label: "Analytics", icon: <BarChart3 size={18} /> },
    { to: "/payouts", label: "Payouts", icon: <Wallet size={18} /> },
  ];

  const activeItem = navItems.find(
    (item) => location.pathname === item.to || location.pathname.startsWith(`${item.to}/`),
  );
  const sectionTitle = activeItem?.label ?? t("app.title");
  const contextLabel = buildContextLabel(sectionTitle, location.pathname, activeItem?.to);

  return (
    <div className="brand-shell neft-page">
      <BrandSidebar items={navItems} title="Partner" />
      <main className="brand-main">
        <BrandHeader
          title={sectionTitle}
          subtitle={contextLabel}
          meta={user?.partnerId ? t("app.partnerLabel", { id: user.partnerId }) : t("app.partnerFallback")}
          userSlot={
            <>
              <div>
                <div className="muted">{t("app.signedInAs")}</div>
                <strong>{user?.email}</strong>
                <div className="roles">{user?.roles.join(", ")}</div>
              </div>
              <button className="ghost neft-btn-secondary" onClick={logout} type="button">
                {t("actions.logout")}
              </button>
            </>
          }
        />
        <div className="brand-content">
          <PageShell key={location.pathname}>
            <Outlet />
          </PageShell>
        </div>
      </main>
    </div>
  );
}
