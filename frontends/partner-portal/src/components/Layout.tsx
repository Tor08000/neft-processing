import { Outlet, useLocation } from "react-router-dom";
import {
  BarChart3,
  Briefcase,
  FileText,
  Package,
  Percent,
  ShoppingBag,
  Wallet,
} from "./icons";
import { useAuth } from "../auth/AuthContext";
import { useLegalGate } from "../auth/LegalGateContext";
import { usePortal } from "../auth/PortalContext";
import { useI18n } from "../i18n";
import { BrandHeader, BrandSidebar, PageShell } from "@shared/brand/components";

export function Layout() {
  const { user, logout } = useAuth();
  const { portal } = usePortal();
  const { isBlocked } = useLegalGate();
  const { t } = useI18n();
  const location = useLocation();
  const capabilities = new Set((portal?.capabilities ?? []).map((cap) => cap.toUpperCase()));

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
    { to: "/products", label: "Products", icon: <Package size={18} />, capability: "PARTNER_PRICING" },
    { to: "/orders", label: "Orders", icon: <ShoppingBag size={18} />, capability: "PARTNER_CORE" },
    { to: "/bookings", label: "Bookings", icon: <Briefcase size={18} />, capability: "PARTNER_CORE" },
    { to: "/promotions", label: "Promotions", icon: <Percent size={18} />, capability: "PARTNER_PRICING" },
    { to: "/analytics", label: "Analytics", icon: <BarChart3 size={18} />, capability: "PARTNER_CORE" },
    { to: "/finance", label: "Финансы", icon: <Wallet size={18} />, capability: "PARTNER_FINANCE_VIEW" },
    { to: "/payouts", label: "Выплаты", icon: <Wallet size={18} />, capability: "PARTNER_PAYOUT_REQUEST" },
    { to: "/documents", label: "Документы", icon: <FileText size={18} />, capability: "PARTNER_DOCUMENTS_LIST" },
    { to: "/legal", label: "Legal", icon: <Package size={18} /> },
  ];

  const visibleNavItems = (isBlocked ? navItems.filter((item) => item.to === "/legal") : navItems).filter(
    (item) => !item.capability || capabilities.has(item.capability),
  );
  const activeItem = visibleNavItems.find(
    (item) => location.pathname === item.to || location.pathname.startsWith(`${item.to}/`),
  );
  const sectionTitle = activeItem?.label ?? t("app.title");
  const contextLabel = buildContextLabel(sectionTitle, location.pathname, activeItem?.to);

  return (
    <div className="brand-shell neft-page">
      <BrandSidebar items={visibleNavItems} title="Partner" />
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
