import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { ClientProvider } from "./auth/ClientContext";
import { LegalGateProvider } from "./auth/LegalGateContext";
import type { AuthSession } from "./api/types";
import { ClientLayout } from "./layout/ClientLayout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { ModuleGate } from "./components/ModuleGate";
import { AccessGate } from "./components/AccessGate";
import { LoginPage } from "./pages/LoginPage";
import { SignupPage } from "./pages/SignupPage";
import { OnboardingPage } from "./pages/OnboardingPage";
import { OnboardingSelfRegistrationPage } from "./pages/OnboardingSelfRegistrationPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { UnauthorizedPage } from "./pages/UnauthorizedPage";
import { OverviewPage } from "./pages/OverviewPage";
import { OperationsPage } from "./pages/OperationsPage";
import { OperationDetailsPage } from "./pages/OperationDetailsPage";
import { ClientCardsPage } from "./pages/ClientCardsPage";
import { ClientCardDetailsPage } from "./pages/ClientCardDetailsPage";
import { LimitTemplatesPage } from "./pages/LimitTemplatesPage";
import { BalancesPage } from "./pages/BalancesPage";
import { ProfilePage } from "./pages/ProfilePage";
import { ClientInvoicesPage } from "./pages/ClientInvoicesPage";
import { ClientInvoiceDetailsPage } from "./pages/ClientInvoiceDetailsPage";
import { ClientContractsPage } from "./pages/ClientContractsPage";
import { ClientContractDetailsPage } from "./pages/ClientContractDetailsPage";
import { FinanceExportsPage } from "./pages/FinanceExportsPage";
import { FinanceExportDetailsPage } from "./pages/FinanceExportDetailsPage";
import { ReconciliationRequestsPage } from "./pages/ReconciliationRequestsPage";
import { ClientDocumentsPage } from "./pages/ClientDocumentsPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { ClientDocumentDetailsPage } from "./pages/ClientDocumentDetailsPage";
import { ClientDocsListPage } from "./pages/ClientDocsListPage";
import { ExplainPage } from "./pages/ExplainPage";
import { ExplainInsightsPage } from "./pages/ExplainInsightsPage";
import { ActionsPage } from "./pages/ActionsPage";
import { useAuth } from "./auth/AuthContext";
import { useClient } from "./auth/ClientContext";
import { AccessState, resolveAccessState } from "./access/accessState";
import { AppLoadingState } from "./components/states";
import { isDemoClient } from "@shared/demo/demo";
import { SettingsPage } from "./pages/SettingsPage";
import { ClientControlsPage } from "./pages/ClientControlsPage";
import { MarketplaceCatalogPage } from "./pages/MarketplaceCatalogPage";
import { MarketplaceProductDetailsPage } from "./pages/MarketplaceProductDetailsPage";
import { MarketplaceOrdersPage } from "./pages/MarketplaceOrdersPage";
import { MarketplaceOrderDetailsPage } from "./pages/MarketplaceOrderDetailsPage";
import { SupportTicketsPage } from "./pages/SupportTicketsPage";
import { SupportTicketDetailsPage } from "./pages/SupportTicketDetailsPage";
import { SupportTicketNewPage } from "./pages/SupportTicketNewPage";
import { CasesPage } from "./pages/CasesPage";
import { CaseDetailsPage } from "./pages/CaseDetailsPage";
import { NotificationsPage } from "./pages/NotificationsPage";
import { ClientAnalyticsPage } from "./pages/ClientAnalyticsPage";
import { AnalyticsDayPage } from "./pages/AnalyticsDayPage";
import { AnalyticsCardPage } from "./pages/AnalyticsCardPage";
import { AnalyticsDriverPage } from "./pages/AnalyticsDriverPage";
import { AnalyticsSupportPage } from "./pages/AnalyticsSupportPage";
import { AnalyticsDashboardPage } from "./pages/AnalyticsDashboardPage";
import { AnalyticsSpendPage } from "./pages/AnalyticsSpendPage";
import { AnalyticsDeclinesPage } from "./pages/AnalyticsDeclinesPage";
import { AnalyticsMarketplacePage } from "./pages/AnalyticsMarketplacePage";
import { AnalyticsDocumentsPage } from "./pages/AnalyticsDocumentsPage";
import { AnalyticsExportsPage } from "./pages/AnalyticsExportsPage";
import { SubscriptionPage } from "./pages/SubscriptionPage";
import { FleetCardsPage } from "./pages/FleetCardsPage";
import { FleetCardDetailsPage } from "./pages/FleetCardDetailsPage";
import { FleetGroupsPage } from "./pages/FleetGroupsPage";
import { FleetGroupDetailsPage } from "./pages/FleetGroupDetailsPage";
import { FleetEmployeesPage } from "./pages/FleetEmployeesPage";
import { FleetSpendPage } from "./pages/FleetSpendPage";
import { FleetNotificationsPage } from "./pages/FleetNotificationsPage";
import { FleetNotificationPoliciesPage } from "./pages/FleetNotificationPoliciesPage";
import { FleetNotificationChannelsPage } from "./pages/FleetNotificationChannelsPage";
import { FleetPoliciesPage } from "./pages/FleetPoliciesPage";
import { FleetPolicyExecutionsPage } from "./pages/FleetPolicyExecutionsPage";
import { FleetPolicyCenterOverviewPage } from "./pages/FleetPolicyCenterOverviewPage";
import { FleetIncidentsPage } from "./pages/FleetIncidentsPage";
import { FleetIncidentDetailsPage } from "./pages/FleetIncidentDetailsPage";
import { FleetPage } from "./pages/logistics/FleetPage";
import { TripDetailsPage } from "./pages/logistics/TripDetailsPage";
import { TripsPage } from "./pages/logistics/TripsPage";
import { FuelControlPage } from "./pages/logistics/FuelControlPage";
import { StationsMapPage } from "./pages/stations/StationsMapPage";
import { AuditPage } from "./pages/AuditPage";
import { isPwaMode } from "./pwa/mode";
import { LegalPage } from "./pages/LegalPage";
import { ReportsPage } from "./pages/ReportsPage";
import { ExportsPage } from "./pages/ExportsPage";
import { ServiceSloPage } from "./pages/ServiceSloPage";
import { BillingOverduePage } from "./pages/BillingOverduePage";
import { ServiceUnavailablePage } from "./pages/ServiceUnavailablePage";
import { TechErrorPage } from "./pages/TechErrorPage";
import { API_BASE_URL } from "./api/base";
import { ONBOARDING_CONTRACT_ROUTE, ONBOARDING_PLAN_ROUTE, ONBOARDING_ROUTE, toCanonicalOnboardingPath } from "./lib/onboardingRoute";

interface AppProps {
  initialSession?: AuthSession | null;
}

const onboardingAliasPaths = new Set([
  "/client/onboarding",
  "/client/onboarding/plan",
  "/client/onboarding/contract",
  "/client/client/onboarding",
  "/client/client/onboarding/plan",
  "/client/client/onboarding/contract",
]);

export function resolveLogicalRoute(pathname: string): string {
  if ([ONBOARDING_ROUTE, ONBOARDING_PLAN_ROUTE, ONBOARDING_CONTRACT_ROUTE].includes(pathname)) {
    return "onboarding";
  }
  if (onboardingAliasPaths.has(pathname)) {
    return "onboarding_alias";
  }
  if (pathname.startsWith("/operations")) {
    return "operations";
  }
  if (pathname.startsWith("/dashboard")) {
    return "dashboard";
  }
  return "other";
}

function IndexRedirect() {
  const { user, authStatus } = useAuth();
  const { client, isLoading, portalState } = useClient();
  const isDemoClientAccount = isDemoClient(user?.email ?? client?.user?.email ?? null);

  if (authStatus !== "authenticated" || !user) {
    return <Navigate to="/login" replace />;
  }

  if (portalState === "LOADING" || isLoading) {
    return <AppLoadingState label="Загружаем профиль..." />;
  }

  const decision = resolveAccessState({ client });
  if (
    !isDemoClientAccount &&
    [AccessState.NEEDS_ONBOARDING, AccessState.NEEDS_PLAN, AccessState.NEEDS_CONTRACT].includes(decision.state)
  ) {
    return <Navigate to={ONBOARDING_ROUTE} replace />;
  }

  return (
    <AccessGate title="Дашборд" capability="CLIENT_DASHBOARD">
      <OverviewPage />
    </AccessGate>
  );
}


function LoginEntryRoute() {
  const { user, authStatus } = useAuth();
  const { client, isLoading, portalState } = useClient();

  if (authStatus === "loading") {
    return <AppLoadingState label="Проверяем сессию..." />;
  }

  if (authStatus === "authenticated" && user) {
    const isDemoClientAccount = isDemoClient(user.email ?? client?.user?.email ?? null);
    if (portalState === "LOADING" || isLoading) {
      return <AppLoadingState label="Загружаем профиль..." />;
    }

    if (isDemoClientAccount) {
      return <Navigate to="/dashboard" replace />;
    }

    const decision = resolveAccessState({ client });
    const needsOnboarding = [AccessState.NEEDS_ONBOARDING, AccessState.NEEDS_PLAN, AccessState.NEEDS_CONTRACT].includes(
      decision.state,
    );

    return <Navigate to={needsOnboarding ? ONBOARDING_ROUTE : "/dashboard"} replace />;
  }

  return <LoginPage />;
}

function PwaIndexRedirect() {
  const { user, authStatus } = useAuth();
  if (authStatus === "authenticated" && user) {
    return <Navigate to="/marketplace/orders" replace />;
  }
  return <Navigate to="/login" replace />;
}


export function OnboardingCanonicalizer() {
  const location = useLocation();
  const canonicalPath = toCanonicalOnboardingPath(location.pathname);

  if (import.meta.env.DEV) {
    console.info("[routing:resolve]", {
      source: "OnboardingCanonicalizer",
      pathname: location.pathname,
      logical_route: resolveLogicalRoute(location.pathname),
      component: canonicalPath === location.pathname ? "OnboardingPage" : "Navigate",
      redirect_target: canonicalPath === location.pathname ? null : canonicalPath,
    });
  }

  if (canonicalPath !== location.pathname) {
    return <Navigate to={canonicalPath} replace />;
  }

  return <OnboardingPage />;
}


function DevRuntimeDiagnostics() {
  const { authStatus } = useAuth();
  const { portalState, client } = useClient();
  const location = useLocation();

  useEffect(() => {
    if (!import.meta.env.DEV) {
      return;
    }
    console.log("API_BASE", API_BASE_URL);
    console.log("AuthStatus", authStatus);
    console.log("CurrentPath", window.location.pathname || location.pathname);
    console.log("LogicalRoute", resolveLogicalRoute(location.pathname));
    console.log("PortalState", portalState);
    console.log("AccessState", client?.access_state ?? null);
  }, [authStatus, client?.access_state, location.pathname, portalState]);

  return null;
}

export function App({ initialSession = null }: AppProps) {
  return (
    <AuthProvider initialSession={initialSession}>
      <ClientProvider>
        <LegalGateProvider>
          <DevRuntimeDiagnostics />
          <Routes>
            <Route path="/login" element={<LoginEntryRoute />} />
            <Route path="/register" element={<SignupPage />} />
            <Route path="/client/login" element={<Navigate to="/login" replace />} />
            <Route path="/client/signup" element={<Navigate to="/register" replace />} />
            <Route path="/unauthorized" element={<UnauthorizedPage />} />
            <Route path="/client/onboarding/start" element={<Navigate to="/onboarding/start" replace />} />
            <Route path="/onboarding/start" element={<OnboardingSelfRegistrationPage mode="start" />} />
            <Route path="/client/onboarding/form" element={<Navigate to="/onboarding/form" replace />} />
            <Route path="/onboarding/form" element={<OnboardingSelfRegistrationPage mode="form" />} />
            <Route path="/client/onboarding/status" element={<Navigate to="/onboarding/status" replace />} />
            <Route path="/onboarding/status" element={<OnboardingSelfRegistrationPage mode="status" />} />
            <Route element={<ProtectedRoute />}>
              <Route path="/client/dashboard" element={<Navigate to="/dashboard" replace />} />
              <Route path="/client/connect" element={<Navigate to="/onboarding" replace />} />
              <Route path="/client/onboarding" element={<OnboardingCanonicalizer />} />
              <Route path="/client/onboarding/plan" element={<OnboardingCanonicalizer />} />
              <Route path="/client/onboarding/contract" element={<OnboardingCanonicalizer />} />
              <Route path="/client/client/onboarding" element={<OnboardingCanonicalizer />} />
              <Route path="/client/client/onboarding/plan" element={<OnboardingCanonicalizer />} />
              <Route path="/client/client/onboarding/contract" element={<OnboardingCanonicalizer />} />
              <Route path="/client/billing/overdue" element={<Navigate to="/billing/overdue" replace />} />
              <Route path="/client/service-unavailable" element={<ServiceUnavailablePage />} />
              <Route path="/client/tech-error" element={<TechErrorPage />} />
              <Route path={ONBOARDING_ROUTE} element={<OnboardingCanonicalizer />} />
              <Route path={ONBOARDING_PLAN_ROUTE} element={<OnboardingCanonicalizer />} />
              <Route path={ONBOARDING_CONTRACT_ROUTE} element={<OnboardingCanonicalizer />} />
              <Route element={<ClientLayout pwaMode={isPwaMode} />}>
              {isPwaMode ? (
                <>
                  <Route index element={<PwaIndexRedirect />} />
                  <Route path="/marketplace/orders" element={<MarketplaceOrdersPage />} />
                  <Route path="/marketplace/orders/:orderId" element={<MarketplaceOrderDetailsPage />} />
                  <Route path="/documents" element={<ClientDocumentsPage />} />
                  <Route path="/documents/:id" element={<ClientDocumentDetailsPage />} />
                  <Route path="/legal" element={<LegalPage />} />
                </>
              ) : (
                <>
                  <Route index element={<IndexRedirect />} />
                  <Route
                    path="/dashboard"
                    element={
                      <AccessGate title="Дашборд" capability="CLIENT_DASHBOARD">
                        <OverviewPage />
                      </AccessGate>
                    }
                  />
                  <Route
                    path="/vehicles"
                    element={
                      <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                        <FleetGroupsPage />
                      </ModuleGate>
                    }
                  />
                  <Route
                    path="/vehicles/:id"
                    element={
                      <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                        <FleetGroupDetailsPage />
                      </ModuleGate>
                    }
                  />
                  <Route
                    path="/cards"
                    element={
                      <AccessGate title="Карты">
                        <ClientCardsPage />
                      </AccessGate>
                    }
                  />
                  <Route path="/limits/templates" element={<LimitTemplatesPage />} />
                  <Route path="/cards/:id" element={<ClientCardDetailsPage />} />
                  <Route path="/cards/:id/limits" element={<ClientCardDetailsPage />} />
                  <Route path="/cards/:id/access" element={<ClientCardDetailsPage />} />
                  <Route
                    path="/orders"
                    element={
                      <ModuleGate module="MARKETPLACE" capability="MARKETPLACE" title="Маркетплейс">
                        <MarketplaceOrdersPage />
                      </ModuleGate>
                    }
                  />
                  <Route
                    path="/orders/:orderId"
                    element={
                      <ModuleGate module="MARKETPLACE" capability="MARKETPLACE" title="Маркетплейс">
                        <MarketplaceOrderDetailsPage />
                      </ModuleGate>
                    }
                  />
                <Route
                  path="/billing"
                  element={
                    <ModuleGate module="DOCS" capability="CLIENT_BILLING" title="Биллинг">
                      <ClientInvoicesPage />
                    </ModuleGate>
                  }
                />
                <Route path="/billing/overdue" element={<BillingOverduePage />} />
                  <Route
                    path="/billing/:id"
                    element={
                      <ModuleGate module="DOCS" capability="CLIENT_BILLING" title="Биллинг">
                        <ClientInvoiceDetailsPage />
                      </ModuleGate>
                    }
                  />
                  <Route
                    path="/client/support"
                    element={
                      <AccessGate title="Поддержка">
                        <SupportTicketsPage />
                      </AccessGate>
                    }
                  />
                  <Route
                    path="/client/support/new"
                    element={
                      <AccessGate title="Поддержка">
                        <SupportTicketNewPage />
                      </AccessGate>
                    }
                  />
                  <Route
                    path="/client/support/:id"
                    element={
                      <AccessGate title="Поддержка">
                        <SupportTicketDetailsPage />
                      </AccessGate>
                    }
                  />
                <Route path="/client/notifications" element={<NotificationsPage />} />
                <Route
                  path="/client/analytics"
                  element={
                    <ModuleGate module="ANALYTICS" capability="CLIENT_ANALYTICS" title="Аналитика">
                      <ClientAnalyticsPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/client/analytics/day"
                  element={
                    <ModuleGate module="ANALYTICS" capability="CLIENT_ANALYTICS" title="Аналитика">
                      <AnalyticsDayPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/client/analytics/card/:cardId"
                  element={
                    <ModuleGate module="ANALYTICS" capability="CLIENT_ANALYTICS" title="Аналитика">
                      <AnalyticsCardPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/client/analytics/driver/:userId"
                  element={
                    <ModuleGate module="ANALYTICS" capability="CLIENT_ANALYTICS" title="Аналитика">
                      <AnalyticsDriverPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/client/analytics/support"
                  element={
                    <ModuleGate module="ANALYTICS" capability="CLIENT_ANALYTICS" title="Аналитика">
                      <AnalyticsSupportPage />
                    </ModuleGate>
                  }
                />
                <Route path="/support" element={<Navigate to="/client/support" replace />} />
                <Route path="/support/:id" element={<SupportTicketDetailsPage />} />
                <Route
                  path="/analytics"
                  element={
                    <ModuleGate module="ANALYTICS" capability="CLIENT_ANALYTICS" title="Аналитика">
                      <AnalyticsDashboardPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/analytics/spend"
                  element={
                    <ModuleGate module="ANALYTICS" capability="CLIENT_ANALYTICS" title="Аналитика">
                      <AnalyticsSpendPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/analytics/declines"
                  element={
                    <ModuleGate module="ANALYTICS" capability="CLIENT_ANALYTICS" title="Аналитика">
                      <AnalyticsDeclinesPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/analytics/marketplace"
                  element={
                    <ModuleGate module="ANALYTICS" capability="CLIENT_ANALYTICS" title="Аналитика">
                      <AnalyticsMarketplacePage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/analytics/documents"
                  element={
                    <ModuleGate module="ANALYTICS" capability="CLIENT_ANALYTICS" title="Аналитика">
                      <AnalyticsDocumentsPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/analytics/exports"
                  element={
                    <ModuleGate module="ANALYTICS" capability="CLIENT_ANALYTICS" title="Аналитика">
                      <AnalyticsExportsPage />
                    </ModuleGate>
                  }
                />
                <Route path="/spend/transactions" element={<OperationsPage />} />
                <Route path="/explain" element={<ExplainPage />} />
                <Route path="/explain/insights" element={<ExplainInsightsPage />} />
                <Route path="/explain/:id" element={<ExplainPage />} />
                <Route path="/documents" element={<ClientDocumentsPage />} />
                <Route path="/documents/:id" element={<ClientDocumentDetailsPage />} />
                <Route path="/exports" element={<FinanceExportsPage />} />
                <Route path="/exports/:id" element={<FinanceExportDetailsPage />} />
                <Route path="/actions" element={<ActionsPage />} />
                <Route path="/invoices" element={<ClientInvoicesPage />} />
                <Route path="/invoices/:id" element={<ClientInvoiceDetailsPage />} />
                <Route path="/contracts" element={<ClientContractsPage />} />
                <Route path="/contracts/:id" element={<ClientContractDetailsPage />} />
                <Route path="/finance/invoices" element={<ClientInvoicesPage />} />
                <Route path="/finance/invoices/:id" element={<ClientInvoiceDetailsPage />} />
                <Route path="/finance/invoices/:id/messages" element={<ClientInvoiceDetailsPage />} />
                <Route path="/finance/documents" element={<Navigate to="/client/documents" replace />} />
                <Route path="/client/documents" element={<DocumentsPage />} />
                <Route path="/client/documents/:id" element={<ClientDocumentDetailsPage />} />
                <Route
                  path="/client/docs/contracts"
                  element={
                    <AccessGate title="Документы">
                      <ClientDocsListPage title="Договоры" docType="CONTRACT" />
                    </AccessGate>
                  }
                />
                <Route
                  path="/client/docs/invoices"
                  element={
                    <AccessGate title="Документы">
                      <ClientDocsListPage title="Счета" docType="INVOICE" />
                    </AccessGate>
                  }
                />
                <Route
                  path="/client/docs/acts"
                  element={
                    <AccessGate title="Документы">
                      <ClientDocsListPage title="Акты" docType="ACT" />
                    </AccessGate>
                  }
                />
                <Route path="/finance/reconciliation" element={<ReconciliationRequestsPage />} />
                <Route path="/finance/exports" element={<FinanceExportsPage />} />
                <Route path="/operations" element={<OperationsPage />} />
                <Route path="/operations/:id" element={<OperationDetailsPage />} />
                <Route path="/balances" element={<BalancesPage />} />
                <Route
                  path="/marketplace"
                  element={
                    <ModuleGate module="MARKETPLACE" capability="MARKETPLACE" title="Маркетплейс">
                      <MarketplaceCatalogPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/marketplace/products/:productId"
                  element={
                    <ModuleGate module="MARKETPLACE" capability="MARKETPLACE" title="Маркетплейс">
                      <MarketplaceProductDetailsPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/marketplace/orders"
                  element={
                    <ModuleGate module="MARKETPLACE" capability="MARKETPLACE" title="Маркетплейс">
                      <MarketplaceOrdersPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/marketplace/orders/:orderId"
                  element={
                    <ModuleGate module="MARKETPLACE" capability="MARKETPLACE" title="Маркетплейс">
                      <MarketplaceOrderDetailsPage />
                    </ModuleGate>
                  }
                />
                <Route path="/support/requests" element={<Navigate to="/client/support" replace />} />
                <Route path="/support/requests/:id" element={<SupportTicketDetailsPage />} />
                <Route path="/cases" element={<CasesPage />} />
                <Route path="/cases/:id" element={<CaseDetailsPage />} />
                <Route path="/subscription" element={<SubscriptionPage />} />
                <Route path="/profile" element={<ProfilePage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/client/settings" element={<Navigate to="/settings" replace />} />
                <Route path="/settings/management" element={<ClientControlsPage />} />
                <Route path="/client/limits" element={<Navigate to="/limits/templates" replace />} />
                <Route path="/client/fleet" element={<Navigate to="/fleet/groups" replace />} />
                <Route path="/client/analytics/dashboard" element={<Navigate to="/analytics" replace />} />
                <Route path="/audit" element={<AuditPage />} />
                <Route
                  path="/client/reports"
                  element={
                    <AccessGate title="Отчёты">
                      <ReportsPage />
                    </AccessGate>
                  }
                />
                <Route
                  path="/client/exports"
                  element={
                    <AccessGate title="Экспорты">
                      <ExportsPage />
                    </AccessGate>
                  }
                />
                <Route path="/client/slo" element={<ServiceSloPage />} />
                <Route path="/legal" element={<LegalPage />} />
                <Route
                  path="/fleet/cards"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <FleetCardsPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/cards/:id"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <FleetCardDetailsPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/groups"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <FleetGroupsPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/groups/:id"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <FleetGroupDetailsPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/employees"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <FleetEmployeesPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/spend"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <FleetSpendPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/notifications"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <FleetNotificationsPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/incidents"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <FleetIncidentsPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/incidents/:id"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <FleetIncidentDetailsPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/policy-center"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <FleetPolicyCenterOverviewPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/policy-center/actions"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <FleetPoliciesPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/policy-center/notifications"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <FleetNotificationPoliciesPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/policy-center/channels"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <FleetNotificationChannelsPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/policy-center/executions"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <FleetPolicyExecutionsPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/logistics/fleet"
                  element={
                    <ModuleGate module="LOGISTICS" capability="LOGISTICS" title="Логистика">
                      <FleetPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/logistics/trips"
                  element={
                    <ModuleGate module="LOGISTICS" capability="LOGISTICS" title="Логистика">
                      <TripsPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/logistics/trips/:tripId"
                  element={
                    <ModuleGate module="LOGISTICS" capability="LOGISTICS" title="Логистика">
                      <TripDetailsPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/logistics/fuel-control"
                  element={
                    <ModuleGate module="LOGISTICS" capability="LOGISTICS" title="Логистика">
                      <FuelControlPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/stations-map"
                  element={
                    <AccessGate title="Карта станций">
                      <StationsMapPage />
                    </AccessGate>
                  }
                />
                <Route path="/logistics/stations-map" element={<Navigate to="/stations-map" replace />} />
                <Route path="/fleet/notifications/policies" element={<Navigate to="/fleet/policy-center/notifications" replace />} />
                <Route path="/fleet/notifications/channels" element={<Navigate to="/fleet/policy-center/channels" replace />} />
                <Route path="/fleet/policies" element={<Navigate to="/fleet/policy-center/actions" replace />} />
                <Route path="/fleet/policies/executions" element={<Navigate to="/fleet/policy-center/executions" replace />} />
                </>
              )}
              </Route>
            </Route>
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </LegalGateProvider>
      </ClientProvider>
    </AuthProvider>
  );
}
