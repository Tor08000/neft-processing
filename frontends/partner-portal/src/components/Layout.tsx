import { useMemo } from "react";
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
import { useTranslation } from "react-i18next";
import { BrandHeader, BrandSidebar, PageShell } from "@shared/brand/components";
import { usePartnerSubscription } from "../auth/PartnerSubscriptionContext";
import { resolveEffectivePartnerRoles, resolvePartnerPortalSurface } from "../access/partnerWorkspace";

export function Layout() {
  const { user, logout } = useAuth();
  const { portal } = usePortal();
  const { isBlocked, isFeatureDisabled } = useLegalGate();
  const { t } = useTranslation();
  const { draft } = usePartnerSubscription();
  const location = useLocation();
  const surface = useMemo(() => resolvePartnerPortalSurface(portal), [portal]);
  const partnerOnboardingActive =
    portal?.access_state === "NEEDS_ONBOARDING" && portal?.access_reason === "partner_onboarding";
  const effectiveRoles = resolveEffectivePartnerRoles(portal, user?.roles);
  const roleSet = new Set([...effectiveRoles, ...(portal?.org_roles ?? [])].map((role) => role.toUpperCase()));
  const hasCapability = (capability?: string) => (capability ? surface.capabilities.has(capability.toUpperCase()) : true);
  const hasRoles = (requiredRoles?: string[]) =>
    requiredRoles?.length ? requiredRoles.some((role) => roleSet.has(role.toUpperCase())) : true;
  const hasWorkspace = (workspace?: string) =>
    workspace ? surface.workspaceCodes.has(workspace as never) : true;

  type NavItem = {
    to: string;
    label: string;
    icon: JSX.Element;
    workspace?: "finance" | "marketplace" | "services" | "support" | "profile";
    capability?: string;
    requiredRoles?: string[];
    hidden?: boolean;
    matchPaths?: string[];
  };

  const buildContextLabel = (section: string, path: string, basePath?: string) => {
    if (!basePath) return section;
    const suffix = path.replace(basePath, "");
    const trail = suffix
      .split("/")
      .filter(Boolean)
      .map((segment) => decodeURIComponent(segment));
    return trail.length ? `${section} · ${trail.join(" / ")}` : section;
  };

  const NAV_ITEMS: NavItem[] = [
    { to: "/onboarding", label: "Onboarding", icon: <Briefcase size={18} />, hidden: !partnerOnboardingActive },
    { to: "/dashboard", label: t("nav.dashboard"), icon: <BarChart3 size={18} /> },
    { to: "/products", label: t("nav.products"), icon: <Package size={18} />, workspace: "marketplace", capability: "PARTNER_CATALOG" },
    { to: "/marketplace/offers", label: t("nav.marketplaceOffers"), icon: <Percent size={18} />, workspace: "marketplace", capability: "PARTNER_PRICING" },
    { to: "/orders", label: t("nav.orders"), icon: <ShoppingBag size={18} />, workspace: "marketplace", capability: "PARTNER_ORDERS" },
    { to: "/analytics", label: t("nav.analytics"), icon: <BarChart3 size={18} />, workspace: "marketplace", capability: "PARTNER_ANALYTICS" },
    { to: "/services", label: t("nav.services"), icon: <Briefcase size={18} />, workspace: "services", capability: "PARTNER_CORE" },
    { to: "/service-requests", label: t("nav.serviceRequests"), icon: <Briefcase size={18} />, workspace: "services", capability: "PARTNER_CORE" },
    { to: "/finance", label: t("nav.finance"), icon: <Wallet size={18} />, workspace: "finance", capability: "PARTNER_FINANCE_VIEW" },
    { to: "/payouts", label: t("nav.payouts"), icon: <Wallet size={18} />, workspace: "finance", capability: "PARTNER_PAYOUT_REQUEST" },
    { to: "/documents", label: t("nav.documents"), icon: <FileText size={18} />, workspace: "finance", capability: "PARTNER_DOCUMENTS_LIST" },
    {
      to: "/support/requests",
      label: t("nav.supportRequests"),
      icon: <FileText size={18} />,
      workspace: "support",
      matchPaths: ["/cases"],
    },
    { to: "/legal", label: t("nav.legal"), icon: <Package size={18} /> },
    { to: "/partner/profile", label: t("nav.partnerProfile"), icon: <Briefcase size={18} />, workspace: "profile" },
    {
      to: "/partner/locations",
      label: t("nav.locations"),
      icon: <Package size={18} />,
      workspace: "profile",
      hidden: !["SERVICE_PARTNER", "FUEL_PARTNER", "LOGISTICS_PARTNER"].includes(surface.kind),
    },
    { to: "/partner/users", label: t("nav.users"), icon: <FileText size={18} />, workspace: "profile" },
    { to: "/partner/terms", label: t("nav.terms"), icon: <FileText size={18} />, workspace: "profile" },
  ];

  const restrictedNavItems = partnerOnboardingActive
    ? NAV_ITEMS.filter((item) => item.to === "/onboarding" || item.to === "/legal" || item.to === "/support/requests")
    : isBlocked
      ? NAV_ITEMS.filter((item) => item.to === "/legal")
      : NAV_ITEMS;
  const visibleNavItems = restrictedNavItems.filter(
    (item) => !item.hidden && hasWorkspace(item.workspace) && hasCapability(item.capability) && hasRoles(item.requiredRoles),
  );
  const routeMatchesNavItem = (item: NavItem) => {
    if (location.pathname === item.to || location.pathname.startsWith(`${item.to}/`)) {
      return true;
    }
    return item.to === "/support/requests" && (location.pathname === "/cases" || location.pathname.startsWith("/cases/"));
  };
  const sidebarItems = visibleNavItems.map((item) => ({
    ...item,
    disabled: false,
    hint: undefined,
  }));
  const activeItem = visibleNavItems.find((item) => routeMatchesNavItem(item));
  const sectionTitle = activeItem?.label ?? t("app.title");
  const contextLabel = buildContextLabel(sectionTitle, location.pathname, activeItem?.to);

  return (
    <div className="brand-shell brand-shell--partner neft-page">
      <BrandSidebar items={sidebarItems} title="Partner" />
      <main className="brand-main">
        <BrandHeader
          title={sectionTitle}
          subtitle={contextLabel}
          meta={user?.partnerId ? `${surface.kind} · ${t("app.partnerLabel", { id: user.partnerId })}` : t("app.partnerFallback")}
          userSlot={
            <>
              <div>
                <div className="muted">{t("app.signedInAs")}</div>
                <strong>{user?.email}</strong>
                <div className="roles">{effectiveRoles.join(", ")}</div>
              </div>
              <button className="ghost neft-btn-secondary" onClick={logout} type="button">
                {t("actions.logout")}
              </button>
            </>
          }
        />
        <div className="brand-content">
          {draft.selectedPlan ? (
            <div className="card">
              <div className="muted">
                {t("app.subscriptionDraft", { plan: draft.selectedPlan, state: draft.subscriptionState ?? "NONE" })}
              </div>
            </div>
          ) : null}
          {isFeatureDisabled ? (
            <div className="card">
              <div className="muted">{t("app.onboardingDisabled")}</div>
            </div>
          ) : null}
          <PageShell key={location.pathname}>
            <Outlet />
          </PageShell>
        </div>
      </main>
    </div>
  );
}
