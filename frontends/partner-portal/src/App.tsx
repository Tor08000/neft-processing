import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { PortalProvider } from "./auth/PortalContext";
import { LegalGateProvider } from "./auth/LegalGateContext";
import { PartnerSubscriptionProvider } from "./auth/PartnerSubscriptionContext";
import type { AuthSession } from "./api/types";
import { Layout } from "./components/Layout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AccessGate } from "./components/AccessGate";
import { EmptyState } from "./components/EmptyState";
import { LoadingState } from "./components/states";
import { usePortal } from "./auth/PortalContext";
import { resolvePartnerPortalSurface } from "./access/partnerWorkspace";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { DashboardPage } from "./pages/DashboardPage";
import { PayoutsPage } from "./pages/payouts/PayoutsPage";
import { DocumentsPage } from "./pages/documents/DocumentsPage";
import { ContractDetailsPage } from "./pages/finance/ContractDetailsPage";
import { ContractsPage } from "./pages/finance/ContractsPage";
import { FinancePage } from "./pages/finance/FinancePage";
import { SettlementDetailsPage } from "./pages/finance/SettlementDetailsPage";
import { SettlementsPage } from "./pages/finance/SettlementsPage";
import { OrdersPage } from "./pages/orders/OrdersPage";
import { OrderDetailsPage } from "./pages/OrderDetailsPage";
import { ServicesCatalogPage } from "./pages/services/ServicesCatalogPage";
import { ServiceDetailsPage } from "./pages/ServiceDetailsPage";
import { ServiceRequestsPage } from "./pages/ServiceRequestsPage";
import { AnalyticsPage } from "./pages/analytics/AnalyticsPage";
import { SupportRequestsPage } from "./pages/SupportRequestsPage";
import { SupportRequestDetailsPage } from "./pages/SupportRequestDetailsPage";
import { MarketplaceProductsPage } from "./pages/MarketplaceProductsPage";
import { MarketplaceOffersPage } from "./pages/MarketplaceOffersPage";
import { LegalPage } from "./pages/LegalPage";
import { PartnerOnboardingPage } from "./pages/PartnerOnboardingPage";
import { PartnerProfileV1Page } from "./pages/PartnerProfileV1Page";
import { PartnerLocationsV1Page } from "./pages/PartnerLocationsV1Page";
import { PartnerUsersV1Page } from "./pages/PartnerUsersV1Page";
import { PartnerTermsV1Page } from "./pages/PartnerTermsV1Page";
import { PartnerConnectPlanPage } from "./pages/PartnerConnectPlanPage";

interface AppProps {
  initialSession?: AuthSession | null;
}

type WorkspaceRouteProps = {
  workspace?: "finance" | "marketplace" | "services" | "support" | "profile";
  capability?: string;
  title?: string;
  children: JSX.Element;
};

type FrozenFinanceContourPageProps = {
  title: string;
  description: string;
};

function PartnerHomeRoute() {
  const { portal, isLoading, portalState } = usePortal();
  if (portalState === "LOADING" || isLoading) {
    return <LoadingState label="Готовим кабинет партнёра..." />;
  }
  if (portal?.access_state === "NEEDS_ONBOARDING" && portal.access_reason === "partner_onboarding") {
    return <Navigate to="/onboarding" replace />;
  }
  const surface = resolvePartnerPortalSurface(portal);
  return <Navigate to={surface.defaultRoute} replace />;
}

function WorkspaceRoute({ workspace, capability, title, children }: WorkspaceRouteProps) {
  const { portal, isLoading, portalState } = usePortal();
  if (portalState === "LOADING" || isLoading) {
    return <LoadingState label="Проверяем доступ..." />;
  }
  const surface = resolvePartnerPortalSurface(portal);
  if (workspace && !surface.workspaceCodes.has(workspace)) {
    return <Navigate to={surface.defaultRoute} replace />;
  }
  return (
    <AccessGate capability={capability} title={title}>
      {children}
    </AccessGate>
  );
}

function FrozenFinanceContourPage({ title, description }: FrozenFinanceContourPageProps) {
  const { pathname } = useLocation();
  if (pathname === "/contracts") {
    return <ContractsPage />;
  }
  if (pathname.startsWith("/contracts/")) {
    return <ContractDetailsPage />;
  }
  if (pathname === "/settlements") {
    return <SettlementsPage />;
  }
  if (pathname.startsWith("/settlements/")) {
    return <SettlementDetailsPage />;
  }

  return (
    <EmptyState
      title={title}
      description={description}
      action={
        <>
          <Link className="primary" to="/finance">
            Открыть финансы
          </Link>
          <Link className="ghost" to="/documents">
            Открыть документы
          </Link>
          <Link className="ghost" to="/support/requests">
            Открыть обращения
          </Link>
        </>
      }
    />
  );
}

export function App({ initialSession = null }: AppProps) {
  return (
    <AuthProvider initialSession={initialSession}>
      <PortalProvider>
        <PartnerSubscriptionProvider>
          <LegalGateProvider>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route element={<ProtectedRoute />}>
                <Route element={<Layout />}>
                  <Route path="/connect/plan" element={<PartnerConnectPlanPage />} />
                  <Route index element={<PartnerHomeRoute />} />
                  <Route path="/onboarding" element={<PartnerOnboardingPage />} />
                  <Route
                    path="/dashboard"
                    element={
                      <AccessGate title="Обзор">
                        <DashboardPage />
                      </AccessGate>
                    }
                  />
                  <Route
                    path="/products"
                    element={
                      <WorkspaceRoute workspace="marketplace" capability="PARTNER_CATALOG" title="Товары">
                        <MarketplaceProductsPage />
                      </WorkspaceRoute>
                    }
                  />
                  <Route
                    path="/products/:id"
                    element={
                      <WorkspaceRoute workspace="marketplace" capability="PARTNER_CATALOG" title="Товары">
                        <MarketplaceProductsPage />
                      </WorkspaceRoute>
                    }
                  />
                  <Route
                    path="/marketplace/offers"
                    element={
                      <WorkspaceRoute workspace="marketplace" capability="PARTNER_PRICING" title="Офферы">
                        <MarketplaceOffersPage />
                      </WorkspaceRoute>
                    }
                  />
                  <Route
                    path="/orders"
                    element={
                      <WorkspaceRoute workspace="marketplace" capability="PARTNER_ORDERS" title="Заказы">
                        <OrdersPage />
                      </WorkspaceRoute>
                    }
                  />
                  <Route
                    path="/orders/:id"
                    element={
                      <WorkspaceRoute workspace="marketplace" capability="PARTNER_ORDERS" title="Заказы">
                        <OrderDetailsPage />
                      </WorkspaceRoute>
                    }
                  />
                  <Route
                    path="/analytics"
                    element={
                      <WorkspaceRoute workspace="marketplace" capability="PARTNER_ANALYTICS" title="Аналитика">
                        <AnalyticsPage />
                      </WorkspaceRoute>
                    }
                  />
                  <Route
                    path="/services"
                    element={
                      <WorkspaceRoute workspace="services" capability="PARTNER_CORE" title="Услуги">
                        <ServicesCatalogPage />
                      </WorkspaceRoute>
                    }
                  />
                  <Route
                    path="/services/:id"
                    element={
                      <WorkspaceRoute workspace="services" capability="PARTNER_CORE" title="Услуги">
                        <ServiceDetailsPage />
                      </WorkspaceRoute>
                    }
                  />
                  <Route
                    path="/service-requests"
                    element={
                      <WorkspaceRoute workspace="services" capability="PARTNER_CORE" title="Заявки услуг">
                        <ServiceRequestsPage />
                      </WorkspaceRoute>
                    }
                  />
                  <Route
                    path="/contracts"
                    element={
                      <WorkspaceRoute workspace="finance" capability="PARTNER_FINANCE_VIEW" title="Контракты">
                        <FrozenFinanceContourPage
                          title="Контур контрактов временно заморожен"
                          description="Отдельный workflow контрактов сейчас не открыт. Используйте финансы, документы и обращения для текущей работы."
                        />
                      </WorkspaceRoute>
                    }
                  />
                  <Route
                    path="/contracts/:id"
                    element={
                      <WorkspaceRoute workspace="finance" capability="PARTNER_FINANCE_VIEW" title="РљРѕРЅС‚СЂР°РєС‚С‹">
                        <FrozenFinanceContourPage title="Contract details" description="Read-only contract details." />
                      </WorkspaceRoute>
                    }
                  />
                  <Route
                    path="/finance"
                    element={
                      <WorkspaceRoute workspace="finance" capability="PARTNER_FINANCE_VIEW" title="Финансы">
                        <FinancePage />
                      </WorkspaceRoute>
                    }
                  />
                  <Route
                    path="/payouts"
                    element={
                      <WorkspaceRoute workspace="finance" capability="PARTNER_PAYOUT_REQUEST" title="Выплаты">
                        <PayoutsPage />
                      </WorkspaceRoute>
                    }
                  />
                  <Route
                    path="/settlements"
                    element={
                      <WorkspaceRoute workspace="finance" capability="PARTNER_FINANCE_VIEW" title="Settlement">
                        <FrozenFinanceContourPage
                          title="Settlement workflow недоступен"
                          description="Отдельный settlement workflow сейчас не открыт. Финансовая сводка остаётся доступной в разделе финансов."
                        />
                      </WorkspaceRoute>
                    }
                  />
                  <Route
                    path="/settlements/:id"
                    element={
                      <WorkspaceRoute workspace="finance" capability="PARTNER_FINANCE_VIEW" title="Settlement">
                        <FrozenFinanceContourPage
                          title="Детали settlement недоступны"
                          description="Глубокая ссылка не открывает отдельную settlement-карточку. Используйте финансы и обращения для текущего контура работы."
                        />
                      </WorkspaceRoute>
                    }
                  />
                  <Route
                    path="/documents"
                    element={
                      <WorkspaceRoute workspace="finance" capability="PARTNER_DOCUMENTS_LIST" title="Документы">
                        <DocumentsPage />
                      </WorkspaceRoute>
                    }
                  />
                  <Route
                    path="/support/requests"
                    element={
                      <WorkspaceRoute workspace="support" title="Обращения">
                        <SupportRequestsPage />
                      </WorkspaceRoute>
                    }
                  />
                  <Route
                    path="/support/requests/:id"
                    element={
                      <WorkspaceRoute workspace="support" title="Обращения">
                        <SupportRequestDetailsPage />
                      </WorkspaceRoute>
                    }
                  />
                  <Route
                    path="/cases"
                    element={
                      <WorkspaceRoute workspace="support" title="Обращения">
                        <SupportRequestsPage />
                      </WorkspaceRoute>
                    }
                  />
                  <Route
                    path="/cases/:id"
                    element={
                      <WorkspaceRoute workspace="support" title="Обращения">
                        <SupportRequestDetailsPage />
                      </WorkspaceRoute>
                    }
                  />
                  <Route
                    path="/legal"
                    element={
                      <WorkspaceRoute workspace="profile" title="Legal">
                        <LegalPage />
                      </WorkspaceRoute>
                    }
                  />
                  <Route
                    path="/partner/profile"
                    element={
                      <WorkspaceRoute workspace="profile" title="Профиль партнёра">
                        <PartnerProfileV1Page />
                      </WorkspaceRoute>
                    }
                  />
                  <Route
                    path="/partner/locations"
                    element={
                      <WorkspaceRoute workspace="profile" title="Локации">
                        <PartnerLocationsV1Page />
                      </WorkspaceRoute>
                    }
                  />
                  <Route
                    path="/partner/users"
                    element={
                      <WorkspaceRoute workspace="profile" title="Пользователи">
                        <PartnerUsersV1Page />
                      </WorkspaceRoute>
                    }
                  />
                  <Route
                    path="/partner/terms"
                    element={
                      <WorkspaceRoute workspace="profile" title="Условия">
                        <PartnerTermsV1Page />
                      </WorkspaceRoute>
                    }
                  />
                </Route>
              </Route>
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </LegalGateProvider>
        </PartnerSubscriptionProvider>
      </PortalProvider>
    </AuthProvider>
  );
}
