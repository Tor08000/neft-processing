import { Suspense, lazy, useEffect } from "react";
import type { ReactNode } from "react";
import { Navigate, Route, Routes, useLocation, useSearchParams } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { ClientProvider } from "./auth/ClientContext";
import { LegalGateProvider } from "./auth/LegalGateContext";
import { ClientJourneyProvider, useClientJourney } from "./auth/ClientJourneyContext";
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
import { DashboardPage } from "./pages/DashboardPage";
import { OperationsPage } from "./pages/OperationsPage";

import { ClientCardsPage } from "./pages/ClientCardsPage";
import { ClientCardDetailsPage } from "./pages/ClientCardDetailsPage";
import { LimitTemplatesPage } from "./pages/LimitTemplatesPage";
import { BalancesPage } from "./pages/BalancesPage";
import { ProfilePage } from "./pages/ProfilePage";






import { ReconciliationRequestsPage } from "./pages/ReconciliationRequestsPage";





import { ExplainInsightsPage } from "./pages/ExplainInsightsPage";
import { ActionsPage } from "./pages/ActionsPage";
import { useAuth } from "./auth/AuthContext";
import { useClient } from "./auth/ClientContext";
import { AppLoadingState } from "./components/states";
import { AppForbiddenState } from "./components/states";











import { NotificationsPage } from "./pages/NotificationsPage";
































import { isPwaMode } from "./pwa/mode";
import { LegalPage } from "./pages/LegalPage";


import { ServiceSloPage } from "./pages/ServiceSloPage";
import { BillingOverduePage } from "./pages/BillingOverduePage";
import { ServiceUnavailablePage } from "./pages/ServiceUnavailablePage";
import { TechErrorPage } from "./pages/TechErrorPage";
import { API_BASE_URL } from "./api/base";
import { ONBOARDING_CONTRACT_ROUTE, ONBOARDING_PLAN_ROUTE, ONBOARDING_ROUTE } from "./lib/onboardingRoute";
import { resolveClientWorkspace } from "./access/clientWorkspace";

const LazyOperationDetailsPage = lazy(() =>
  import("./pages/OperationDetailsPage").then((module) => ({
    default: module.OperationDetailsPage,
  })),
);
const LazyClientContractDetailsPage = lazy(() =>
  import("./pages/ClientContractDetailsPage").then((module) => ({
    default: module.ClientContractDetailsPage,
  })),
);
const LazyDocumentsPage = lazy(() =>
  import("./pages/DocumentsPage").then((module) => ({
    default: module.DocumentsPage,
  })),
);
const LazyClientDocsListPage = lazy(() =>
  import("./pages/ClientDocsListPage").then((module) => ({
    default: module.ClientDocsListPage,
  })),
);
const LazySettingsPage = lazy(() =>
  import("./pages/SettingsPage").then((module) => ({
    default: module.SettingsPage,
  })),
);
const LazyClientControlsPage = lazy(() =>
  import("./pages/ClientControlsPage").then((module) => ({
    default: module.ClientControlsPage,
  })),
);
const LazySupportTicketDetailsPage = lazy(() =>
  import("./pages/SupportTicketDetailsPage").then((module) => ({
    default: module.SupportTicketDetailsPage,
  })),
);
const LazySupportTicketNewPage = lazy(() =>
  import("./pages/SupportTicketNewPage").then((module) => ({
    default: module.SupportTicketNewPage,
  })),
);
const LazyCaseDetailsPage = lazy(() =>
  import("./pages/CaseDetailsPage").then((module) => ({
    default: module.CaseDetailsPage,
  })),
);
const LazyClientInvoicesPage = lazy(() =>
  import("./pages/ClientInvoicesPage").then((module) => ({
    default: module.ClientInvoicesPage,
  })),
);
const LazyClientInvoiceDetailsPage = lazy(() =>
  import("./pages/ClientInvoiceDetailsPage").then((module) => ({
    default: module.ClientInvoiceDetailsPage,
  })),
);
const LazyClientContractsPage = lazy(() =>
  import("./pages/ClientContractsPage").then((module) => ({
    default: module.ClientContractsPage,
  })),
);
const LazyFinanceExportsPage = lazy(() =>
  import("./pages/FinanceExportsPage").then((module) => ({
    default: module.FinanceExportsPage,
  })),
);
const LazyFinanceExportDetailsPage = lazy(() =>
  import("./pages/FinanceExportDetailsPage").then((module) => ({
    default: module.FinanceExportDetailsPage,
  })),
);
const LazyClientDocumentsPage = lazy(() =>
  import("./pages/ClientDocumentsPage").then((module) => ({
    default: module.ClientDocumentsPage,
  })),
);
const LazyClientDocumentDetailsPage = lazy(() =>
  import("./pages/ClientDocumentDetailsPage").then((module) => ({
    default: module.ClientDocumentDetailsPage,
  })),
);
const LazyExplainPage = lazy(() =>
  import("./pages/ExplainPage").then((module) => ({
    default: module.ExplainPage,
  })),
);
const LazyMarketplaceCatalogPage = lazy(() =>
  import("./pages/MarketplaceCatalogPage").then((module) => ({
    default: module.MarketplaceCatalogPage,
  })),
);
const LazySupportTicketsPage = lazy(() =>
  import("./pages/SupportTicketsPage").then((module) => ({
    default: module.SupportTicketsPage,
  })),
);
const LazyCasesPage = lazy(() =>
  import("./pages/CasesPage").then((module) => ({
    default: module.CasesPage,
  })),
);
const LazySubscriptionPage = lazy(() =>
  import("./pages/SubscriptionPage").then((module) => ({
    default: module.SubscriptionPage,
  })),
);
const LazyMarketplaceProductDetailsPage = lazy(() =>
  import("./pages/MarketplaceProductDetailsPage").then((module) => ({
    default: module.MarketplaceProductDetailsPage,
  })),
);
const LazyMarketplaceOrdersPage = lazy(() =>
  import("./pages/MarketplaceOrdersPage").then((module) => ({
    default: module.MarketplaceOrdersPage,
  })),
);
const LazyMarketplaceOrderDetailsPage = lazy(() =>
  import("./pages/MarketplaceOrderDetailsPage").then((module) => ({
    default: module.MarketplaceOrderDetailsPage,
  })),
);
const LazyClientAnalyticsPage = lazy(() =>
  import("./pages/ClientAnalyticsPage").then((module) => ({
    default: module.ClientAnalyticsPage,
  })),
);
const LazyAnalyticsDayPage = lazy(() =>
  import("./pages/AnalyticsDayPage").then((module) => ({
    default: module.AnalyticsDayPage,
  })),
);
const LazyAnalyticsCardPage = lazy(() =>
  import("./pages/AnalyticsCardPage").then((module) => ({
    default: module.AnalyticsCardPage,
  })),
);
const LazyAnalyticsDriverPage = lazy(() =>
  import("./pages/AnalyticsDriverPage").then((module) => ({
    default: module.AnalyticsDriverPage,
  })),
);
const LazyAnalyticsSupportPage = lazy(() =>
  import("./pages/AnalyticsSupportPage").then((module) => ({
    default: module.AnalyticsSupportPage,
  })),
);
const LazyAnalyticsDashboardPage = lazy(() =>
  import("./pages/AnalyticsDashboardPage").then((module) => ({
    default: module.AnalyticsDashboardPage,
  })),
);
const LazyAnalyticsSpendPage = lazy(() =>
  import("./pages/AnalyticsSpendPage").then((module) => ({
    default: module.AnalyticsSpendPage,
  })),
);
const LazyAnalyticsDeclinesPage = lazy(() =>
  import("./pages/AnalyticsDeclinesPage").then((module) => ({
    default: module.AnalyticsDeclinesPage,
  })),
);
const LazyAnalyticsMarketplacePage = lazy(() =>
  import("./pages/AnalyticsMarketplacePage").then((module) => ({
    default: module.AnalyticsMarketplacePage,
  })),
);
const LazyAnalyticsDocumentsPage = lazy(() =>
  import("./pages/AnalyticsDocumentsPage").then((module) => ({
    default: module.AnalyticsDocumentsPage,
  })),
);
const LazyAnalyticsExportsPage = lazy(() =>
  import("./pages/AnalyticsExportsPage").then((module) => ({
    default: module.AnalyticsExportsPage,
  })),
);
const LazyFleetCardsPage = lazy(() =>
  import("./pages/FleetCardsPage").then((module) => ({
    default: module.FleetCardsPage,
  })),
);
const LazyFleetCardDetailsPage = lazy(() =>
  import("./pages/FleetCardDetailsPage").then((module) => ({
    default: module.FleetCardDetailsPage,
  })),
);
const LazyFleetGroupsPage = lazy(() =>
  import("./pages/FleetGroupsPage").then((module) => ({
    default: module.FleetGroupsPage,
  })),
);
const LazyFleetGroupDetailsPage = lazy(() =>
  import("./pages/FleetGroupDetailsPage").then((module) => ({
    default: module.FleetGroupDetailsPage,
  })),
);
const LazyFleetEmployeesPage = lazy(() =>
  import("./pages/FleetEmployeesPage").then((module) => ({
    default: module.FleetEmployeesPage,
  })),
);
const LazyFleetSpendPage = lazy(() =>
  import("./pages/FleetSpendPage").then((module) => ({
    default: module.FleetSpendPage,
  })),
);
const LazyFleetNotificationsPage = lazy(() =>
  import("./pages/FleetNotificationsPage").then((module) => ({
    default: module.FleetNotificationsPage,
  })),
);
const LazyFleetNotificationPoliciesPage = lazy(() =>
  import("./pages/FleetNotificationPoliciesPage").then((module) => ({
    default: module.FleetNotificationPoliciesPage,
  })),
);
const LazyFleetNotificationChannelsPage = lazy(() =>
  import("./pages/FleetNotificationChannelsPage").then((module) => ({
    default: module.FleetNotificationChannelsPage,
  })),
);
const LazyFleetPoliciesPage = lazy(() =>
  import("./pages/FleetPoliciesPage").then((module) => ({
    default: module.FleetPoliciesPage,
  })),
);
const LazyFleetPolicyExecutionsPage = lazy(() =>
  import("./pages/FleetPolicyExecutionsPage").then((module) => ({
    default: module.FleetPolicyExecutionsPage,
  })),
);
const LazyFleetPolicyCenterOverviewPage = lazy(() =>
  import("./pages/FleetPolicyCenterOverviewPage").then((module) => ({
    default: module.FleetPolicyCenterOverviewPage,
  })),
);
const LazyFleetIncidentsPage = lazy(() =>
  import("./pages/FleetIncidentsPage").then((module) => ({
    default: module.FleetIncidentsPage,
  })),
);
const LazyFleetIncidentDetailsPage = lazy(() =>
  import("./pages/FleetIncidentDetailsPage").then((module) => ({
    default: module.FleetIncidentDetailsPage,
  })),
);
const LazyFleetPage = lazy(() =>
  import("./pages/logistics/FleetPage").then((module) => ({
    default: module.FleetPage,
  })),
);
const LazyTripDetailsPage = lazy(() =>
  import("./pages/logistics/TripDetailsPage").then((module) => ({
    default: module.TripDetailsPage,
  })),
);
const LazyTripsPage = lazy(() =>
  import("./pages/logistics/TripsPage").then((module) => ({
    default: module.TripsPage,
  })),
);
const LazyFuelControlPage = lazy(() =>
  import("./pages/logistics/FuelControlPage").then((module) => ({
    default: module.FuelControlPage,
  })),
);
const LazyStationsMapPage = lazy(() =>
  import("./pages/stations/StationsMapPage").then((module) => ({
    default: module.StationsMapPage,
  })),
);
const LazyAuditPage = lazy(() =>
  import("./pages/AuditPage").then((module) => ({
    default: module.AuditPage,
  })),
);
const LazyReportsPage = lazy(() =>
  import("./pages/ReportsPage").then((module) => ({
    default: module.ReportsPage,
  })),
);
const LazyExportsPage = lazy(() =>
  import("./pages/ExportsPage").then((module) => ({
    default: module.ExportsPage,
  })),
);
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

const AUTH_ENTRY_PATHS = ["/login", "/register", "/client/login", "/client/signup", "/client/register", "/unauthorized"];

export function resolveSafeClientReturnUrl(rawReturnUrl: string | null, fallbackRoute: string): string {
  if (!rawReturnUrl || !rawReturnUrl.startsWith("/") || rawReturnUrl.startsWith("//")) {
    return fallbackRoute;
  }
  if (AUTH_ENTRY_PATHS.some((path) => rawReturnUrl === path || rawReturnUrl.startsWith(`${path}?`))) {
    return fallbackRoute;
  }
  return rawReturnUrl;
}

function IndexRedirect() {
  const { user, authStatus } = useAuth();
  const { nextRoute } = useClientJourney();

  if (authStatus !== "authenticated" || !user) {
    return <Navigate to="/login" replace />;
  }

  if (nextRoute !== "/dashboard") {
    return <Navigate to={nextRoute} replace />;
  }

  return (
    <AccessGate title="Дашборд" capability="CLIENT_DASHBOARD" allowDemoBypass={false}>
      <DashboardPage />
    </AccessGate>
  );
}


function LoginEntryRoute() {
  const { user, authStatus } = useAuth();
  const { nextRoute } = useClientJourney();
  const [searchParams] = useSearchParams();
  const returnUrl = resolveSafeClientReturnUrl(searchParams.get("returnUrl"), nextRoute);

  if (authStatus === "loading") {
    return <AppLoadingState label="Проверяем сессию..." />;
  }

  if (authStatus === "authenticated" && user) {
    return <Navigate to={returnUrl} replace />;
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

function CompatRedirect({ to }: { to: string }) {
  const location = useLocation();
  const target = `${to}${location.search}`;
  return <Navigate to={target} replace />;
}


function JourneyRouteEnforcer() {
  const { ensureRoute } = useClientJourney();
  useEffect(() => {
    ensureRoute("App.JourneyRouteEnforcer");
  }, [ensureRoute]);
  return null;
}


function DevRuntimeDiagnostics() {
  const { authStatus } = useAuth();
  const { portalState, client } = useClient();
  const location = useLocation();

  useEffect(() => {
    if (!import.meta.env.DEV || import.meta.env.VITE_CLIENT_DEBUG_DIAGNOSTICS !== "true") {
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

function RouteSuspense({ children }: { children: ReactNode }) {
  return <Suspense fallback={<AppLoadingState label="Загружаем страницу..." />}>{children}</Suspense>;
}

type ClientWorkspaceRouteProps = {
  children: ReactNode;
  title: string;
  workspace: "finance" | "team";
  capability?: string;
  module?: string;
};

function ClientWorkspaceRoute({ children, title, workspace, capability, module }: ClientWorkspaceRouteProps) {
  const { client, isLoading, portalState } = useClient();
  const resolvedWorkspace = resolveClientWorkspace({ client });

  if (portalState === "LOADING" || isLoading) {
    return <AppLoadingState label="Проверяем доступ..." />;
  }

  const isAllowed =
    workspace === "finance" ? resolvedWorkspace.hasFinanceWorkspace : resolvedWorkspace.hasTeamWorkspace;

  const message =
    workspace === "finance"
      ? "Финансовый контур доступен только бизнес-клиентам."
      : "Управление командой доступно только бизнес-клиентам с соответствующей ролью.";

  return (
    <AccessGate title={title} capability={capability} module={module}>
      {isAllowed ? children : <AppForbiddenState message={message} />}
    </AccessGate>
  );
}

export function App({ initialSession = null }: AppProps) {
  return (
    <AuthProvider initialSession={initialSession}>
      <ClientProvider>
        <ClientJourneyProvider>
          <LegalGateProvider>
          <JourneyRouteEnforcer />
          <DevRuntimeDiagnostics />
          <Routes>
            <Route path="/login" element={<LoginEntryRoute />} />
            <Route path="/register" element={<SignupPage />} />
            <Route path="/client/login" element={<CompatRedirect to="/login" />} />
            <Route path="/client/signup" element={<CompatRedirect to="/register" />} />
            <Route path="/client/register" element={<CompatRedirect to="/register" />} />
            <Route path="/unauthorized" element={<UnauthorizedPage />} />
            <Route path="/client/onboarding/start" element={<Navigate to="/onboarding/start" replace />} />
            <Route path="/onboarding/start" element={<OnboardingSelfRegistrationPage mode="start" />} />
            <Route path="/client/onboarding/form" element={<Navigate to="/onboarding/form" replace />} />
            <Route path="/onboarding/form" element={<OnboardingSelfRegistrationPage mode="form" />} />
            <Route path="/client/onboarding/status" element={<Navigate to="/onboarding/status" replace />} />
            <Route path="/onboarding/status" element={<OnboardingSelfRegistrationPage mode="status" />} />
              <Route element={<ProtectedRoute />}>
              <Route path="/client/dashboard" element={<Navigate to="/dashboard" replace />} />
              <Route path="/client/connect" element={<Navigate to={ONBOARDING_ROUTE} replace />} />
              <Route path="/client/onboarding" element={<Navigate to={ONBOARDING_ROUTE} replace />} />
              <Route path="/client/onboarding/plan" element={<Navigate to={ONBOARDING_PLAN_ROUTE} replace />} />
              <Route path="/client/onboarding/contract" element={<Navigate to={ONBOARDING_CONTRACT_ROUTE} replace />} />
              <Route path="/client/client/onboarding" element={<Navigate to={ONBOARDING_ROUTE} replace />} />
              <Route path="/client/client/onboarding/plan" element={<Navigate to={ONBOARDING_PLAN_ROUTE} replace />} />
              <Route path="/client/client/onboarding/contract" element={<Navigate to={ONBOARDING_CONTRACT_ROUTE} replace />} />
              <Route path="/client/billing/overdue" element={<Navigate to="/billing/overdue" replace />} />
              <Route path="/client/service-unavailable" element={<ServiceUnavailablePage />} />
              <Route path="/client/tech-error" element={<TechErrorPage />} />
              <Route element={<ClientLayout pwaMode={isPwaMode} />}>
              {isPwaMode ? (
                <>
                  <Route index element={<PwaIndexRedirect />} />
                  <Route path="/marketplace/orders" element={<RouteSuspense><LazyMarketplaceOrdersPage /></RouteSuspense>} />
                  <Route path="/marketplace/orders/:orderId" element={<RouteSuspense><LazyMarketplaceOrderDetailsPage /></RouteSuspense>} />
                  {/* Legacy closing-docs compatibility routes. /client/documents* is the canonical general docflow; /documents/:id remains the final legacy compatibility tail for closing-doc detail/file/history UX. */}
                  <Route path="/documents" element={<RouteSuspense><LazyClientDocumentsPage /></RouteSuspense>} />
                  <Route path="/documents/:id" element={<RouteSuspense><LazyClientDocumentDetailsPage mode="legacy" /></RouteSuspense>} />
                  <Route path="/legal" element={<LegalPage />} />
                </>
              ) : (
                <>
                  <Route index element={<IndexRedirect />} />
                  <Route path={ONBOARDING_ROUTE} element={<OnboardingPage />} />
                  <Route path={ONBOARDING_PLAN_ROUTE} element={<OnboardingPage />} />
                  <Route path={ONBOARDING_CONTRACT_ROUTE} element={<OnboardingPage />} />
                  <Route path="/connect" element={<Navigate to={ONBOARDING_ROUTE} replace />} />
                  <Route path="/connect/plan" element={<Navigate to={ONBOARDING_PLAN_ROUTE} replace />} />
                  <Route path="/connect/type" element={<Navigate to={ONBOARDING_ROUTE} replace />} />
                  <Route path="/connect/profile" element={<Navigate to={ONBOARDING_ROUTE} replace />} />
                  <Route path="/connect/documents" element={<Navigate to={ONBOARDING_CONTRACT_ROUTE} replace />} />
                  <Route path="/connect/sign" element={<Navigate to={ONBOARDING_CONTRACT_ROUTE} replace />} />
                  <Route path="/connect/payment" element={<Navigate to={ONBOARDING_CONTRACT_ROUTE} replace />} />
                  <Route
                    path="/dashboard"
                    element={
                      <AccessGate title="Дашборд" capability="CLIENT_DASHBOARD" allowDemoBypass={false}>
                        <DashboardPage />
                      </AccessGate>
                    }
                  />
                  <Route
                    path="/vehicles"
                    element={
                      <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                        <RouteSuspense><LazyFleetGroupsPage /></RouteSuspense>
                      </ModuleGate>
                    }
                  />
                  <Route
                    path="/vehicles/:id"
                    element={
                      <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                        <RouteSuspense><LazyFleetGroupDetailsPage /></RouteSuspense>
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
                        <RouteSuspense><LazyMarketplaceOrdersPage /></RouteSuspense>
                      </ModuleGate>
                    }
                  />
                  <Route
                    path="/orders/:orderId"
                    element={
                      <ModuleGate module="MARKETPLACE" capability="MARKETPLACE" title="Маркетплейс">
                        <RouteSuspense><LazyMarketplaceOrderDetailsPage /></RouteSuspense>
                      </ModuleGate>
                    }
                  />
                <Route
                  path="/billing"
                  element={
                    <ClientWorkspaceRoute workspace="finance" module="DOCS" capability="CLIENT_BILLING" title="Биллинг">
                      <RouteSuspense><LazyClientInvoicesPage /></RouteSuspense>
                    </ClientWorkspaceRoute>
                  }
                />
                <Route path="/billing/overdue" element={<BillingOverduePage />} />
                  <Route
                    path="/billing/:id"
                    element={
                      <ClientWorkspaceRoute workspace="finance" module="DOCS" capability="CLIENT_BILLING" title="Биллинг">
                        <RouteSuspense><LazyClientInvoiceDetailsPage /></RouteSuspense>
                      </ClientWorkspaceRoute>
                    }
                  />
                  <Route
                    path="/client/support"
                    element={
                      <AccessGate title="Поддержка">
                        <RouteSuspense><LazySupportTicketsPage /></RouteSuspense>
                      </AccessGate>
                    }
                  />
                  <Route
                    path="/client/support/new"
                    element={
                      <AccessGate title="Поддержка">
                        <RouteSuspense><LazySupportTicketNewPage /></RouteSuspense>
                      </AccessGate>
                    }
                  />
                  <Route
                    path="/client/support/:id"
                    element={
                      <AccessGate title="Поддержка">
                        <RouteSuspense><LazySupportTicketDetailsPage /></RouteSuspense>
                      </AccessGate>
                    }
                  />
                <Route path="/client/notifications" element={<NotificationsPage />} />
                <Route
                  path="/client/analytics"
                  element={
                    <ModuleGate module="ANALYTICS" capability="CLIENT_ANALYTICS" title="Аналитика">
                      <RouteSuspense><LazyClientAnalyticsPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/client/analytics/day"
                  element={
                    <ModuleGate module="ANALYTICS" capability="CLIENT_ANALYTICS" title="Аналитика">
                      <RouteSuspense><LazyAnalyticsDayPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/client/analytics/card/:cardId"
                  element={
                    <ModuleGate module="ANALYTICS" capability="CLIENT_ANALYTICS" title="Аналитика">
                      <RouteSuspense><LazyAnalyticsCardPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/client/analytics/driver/:userId"
                  element={
                    <ModuleGate module="ANALYTICS" capability="CLIENT_ANALYTICS" title="Аналитика">
                      <RouteSuspense><LazyAnalyticsDriverPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/client/analytics/support"
                  element={
                    <ModuleGate module="ANALYTICS" capability="CLIENT_ANALYTICS" title="Аналитика">
                      <RouteSuspense><LazyAnalyticsSupportPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route path="/support" element={<Navigate to="/client/support" replace />} />
                <Route path="/support/:id" element={<RouteSuspense><LazySupportTicketDetailsPage /></RouteSuspense>} />
                <Route
                  path="/analytics"
                  element={
                    <ModuleGate module="ANALYTICS" capability="CLIENT_ANALYTICS" title="Аналитика">
                      <RouteSuspense><LazyAnalyticsDashboardPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/analytics/spend"
                  element={
                    <ModuleGate module="ANALYTICS" capability="CLIENT_ANALYTICS" title="Аналитика">
                      <RouteSuspense><LazyAnalyticsSpendPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/analytics/declines"
                  element={
                    <ModuleGate module="ANALYTICS" capability="CLIENT_ANALYTICS" title="Аналитика">
                      <RouteSuspense><LazyAnalyticsDeclinesPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/analytics/marketplace"
                  element={
                    <ModuleGate module="ANALYTICS" capability="CLIENT_ANALYTICS" title="Аналитика">
                      <RouteSuspense><LazyAnalyticsMarketplacePage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/analytics/documents"
                  element={
                    <ModuleGate module="ANALYTICS" capability="CLIENT_ANALYTICS" title="Аналитика">
                      <RouteSuspense><LazyAnalyticsDocumentsPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/analytics/exports"
                  element={
                    <ModuleGate module="ANALYTICS" capability="CLIENT_ANALYTICS" title="Аналитика">
                      <RouteSuspense><LazyAnalyticsExportsPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route path="/spend/transactions" element={<OperationsPage />} />
                <Route path="/explain" element={<RouteSuspense><LazyExplainPage /></RouteSuspense>} />
                <Route path="/explain/insights" element={<ExplainInsightsPage />} />
                <Route path="/explain/:id" element={<RouteSuspense><LazyExplainPage /></RouteSuspense>} />
                {/* Legacy closing-docs compatibility routes. /client/documents* is the canonical general docflow; /documents/:id remains the final legacy compatibility tail for closing-doc detail/file/history UX. */}
                <Route path="/documents" element={<RouteSuspense><LazyClientDocumentsPage /></RouteSuspense>} />
                <Route path="/documents/:id" element={<RouteSuspense><LazyClientDocumentDetailsPage mode="legacy" /></RouteSuspense>} />
                <Route
                  path="/exports"
                  element={
                    <ClientWorkspaceRoute workspace="finance" title="Экспорты">
                      <RouteSuspense><LazyFinanceExportsPage /></RouteSuspense>
                    </ClientWorkspaceRoute>
                  }
                />
                <Route
                  path="/exports/:id"
                  element={
                    <ClientWorkspaceRoute workspace="finance" title="Экспорты">
                      <RouteSuspense><LazyFinanceExportDetailsPage /></RouteSuspense>
                    </ClientWorkspaceRoute>
                  }
                />
                <Route path="/actions" element={<ActionsPage />} />
                <Route
                  path="/invoices"
                  element={
                    <ClientWorkspaceRoute workspace="finance" module="DOCS" capability="CLIENT_BILLING" title="Финансы">
                      <RouteSuspense><LazyClientInvoicesPage /></RouteSuspense>
                    </ClientWorkspaceRoute>
                  }
                />
                <Route
                  path="/invoices/:id"
                  element={
                    <ClientWorkspaceRoute workspace="finance" module="DOCS" capability="CLIENT_BILLING" title="Финансы">
                      <RouteSuspense><LazyClientInvoiceDetailsPage /></RouteSuspense>
                    </ClientWorkspaceRoute>
                  }
                />
                <Route path="/contracts" element={<RouteSuspense><LazyClientContractsPage /></RouteSuspense>} />
                <Route path="/contracts/:id" element={<RouteSuspense><LazyClientContractDetailsPage /></RouteSuspense>} />
                <Route
                  path="/finance/invoices"
                  element={
                    <ClientWorkspaceRoute workspace="finance" module="DOCS" capability="CLIENT_BILLING" title="Финансы">
                      <RouteSuspense><LazyClientInvoicesPage /></RouteSuspense>
                    </ClientWorkspaceRoute>
                  }
                />
                <Route
                  path="/finance/invoices/:id"
                  element={
                    <ClientWorkspaceRoute workspace="finance" module="DOCS" capability="CLIENT_BILLING" title="Финансы">
                      <RouteSuspense><LazyClientInvoiceDetailsPage /></RouteSuspense>
                    </ClientWorkspaceRoute>
                  }
                />
                <Route
                  path="/finance/invoices/:id/messages"
                  element={
                    <ClientWorkspaceRoute workspace="finance" module="DOCS" capability="CLIENT_BILLING" title="Финансы">
                      <RouteSuspense><LazyClientInvoiceDetailsPage /></RouteSuspense>
                    </ClientWorkspaceRoute>
                  }
                />
                {/* Canonical general client documents/docflow entry points. New generic navigation should land here; /documents/:id stays legacy-only compatibility tail on purpose. */}
                <Route path="/finance/documents" element={<Navigate to="/client/documents" replace />} />
                <Route path="/client/documents" element={<RouteSuspense><LazyDocumentsPage /></RouteSuspense>} />
                <Route path="/client/documents/:id" element={<RouteSuspense><LazyClientDocumentDetailsPage mode="canonical" /></RouteSuspense>} />
                <Route
                  path="/client/docs/contracts"
                  element={
                    <AccessGate title="Документы">
                      <RouteSuspense><LazyClientDocsListPage title="Договоры" docType="CONTRACT" /></RouteSuspense>
                    </AccessGate>
                  }
                />
                <Route
                  path="/client/docs/invoices"
                  element={
                    <AccessGate title="Документы">
                      <RouteSuspense><LazyClientDocsListPage title="Счета" docType="INVOICE" /></RouteSuspense>
                    </AccessGate>
                  }
                />
                <Route
                  path="/client/docs/acts"
                  element={
                    <AccessGate title="Документы">
                      <RouteSuspense><LazyClientDocsListPage title="Акты" docType="ACT" /></RouteSuspense>
                    </AccessGate>
                  }
                />
                <Route
                  path="/finance/reconciliation"
                  element={
                    <ClientWorkspaceRoute workspace="finance" title="Сверка">
                      <ReconciliationRequestsPage />
                    </ClientWorkspaceRoute>
                  }
                />
                <Route
                  path="/finance/exports"
                  element={
                    <ClientWorkspaceRoute workspace="finance" title="Экспорты">
                      <RouteSuspense><LazyFinanceExportsPage /></RouteSuspense>
                    </ClientWorkspaceRoute>
                  }
                />
                <Route path="/operations" element={<OperationsPage />} />
                <Route path="/operations/:id" element={<RouteSuspense><LazyOperationDetailsPage /></RouteSuspense>} />
                <Route
                  path="/balances"
                  element={
                    <ClientWorkspaceRoute workspace="finance" title="Балансы">
                      <BalancesPage />
                    </ClientWorkspaceRoute>
                  }
                />
                <Route
                  path="/marketplace"
                  element={
                    <ModuleGate module="MARKETPLACE" capability="MARKETPLACE" title="Маркетплейс">
                      <RouteSuspense><LazyMarketplaceCatalogPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/marketplace/products/:productId"
                  element={
                    <ModuleGate module="MARKETPLACE" capability="MARKETPLACE" title="Маркетплейс">
                      <RouteSuspense><LazyMarketplaceProductDetailsPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/marketplace/orders"
                  element={
                    <ModuleGate module="MARKETPLACE" capability="MARKETPLACE" title="Маркетплейс">
                      <RouteSuspense><LazyMarketplaceOrdersPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/marketplace/orders/:orderId"
                  element={
                    <ModuleGate module="MARKETPLACE" capability="MARKETPLACE" title="Маркетплейс">
                      <RouteSuspense><LazyMarketplaceOrderDetailsPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route path="/support/requests" element={<Navigate to="/client/support" replace />} />
                <Route path="/support/requests/:id" element={<RouteSuspense><LazySupportTicketDetailsPage /></RouteSuspense>} />
                <Route path="/cases" element={<RouteSuspense><LazyCasesPage /></RouteSuspense>} />
                <Route path="/cases/:id" element={<RouteSuspense><LazyCaseDetailsPage /></RouteSuspense>} />
                <Route path="/subscription" element={<RouteSuspense><LazySubscriptionPage /></RouteSuspense>} />
                <Route path="/profile" element={<ProfilePage />} />
                <Route path="/settings" element={<RouteSuspense><LazySettingsPage /></RouteSuspense>} />
                <Route path="/client/settings" element={<Navigate to="/settings" replace />} />
                <Route
                  path="/settings/management"
                  element={
                    <ClientWorkspaceRoute workspace="team" title="Управление">
                      <RouteSuspense><LazyClientControlsPage /></RouteSuspense>
                    </ClientWorkspaceRoute>
                  }
                />
                <Route path="/client/limits" element={<Navigate to="/limits/templates" replace />} />
                <Route path="/client/fleet" element={<Navigate to="/fleet/groups" replace />} />
                <Route path="/client/analytics/dashboard" element={<Navigate to="/analytics" replace />} />
                <Route path="/audit" element={<RouteSuspense><LazyAuditPage /></RouteSuspense>} />
                <Route
                  path="/client/reports"
                  element={
                    <AccessGate title="Отчёты">
                      <RouteSuspense><LazyReportsPage /></RouteSuspense>
                    </AccessGate>
                  }
                />
                <Route
                  path="/client/exports"
                  element={
                    <AccessGate title="Экспорты">
                      <RouteSuspense><LazyExportsPage /></RouteSuspense>
                    </AccessGate>
                  }
                />
                <Route path="/client/slo" element={<ServiceSloPage />} />
                <Route path="/legal" element={<LegalPage />} />
                <Route
                  path="/fleet/cards"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <RouteSuspense><LazyFleetCardsPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/cards/:id"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <RouteSuspense><LazyFleetCardDetailsPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/groups"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <RouteSuspense><LazyFleetGroupsPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/groups/:id"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <RouteSuspense><LazyFleetGroupDetailsPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/employees"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <RouteSuspense><LazyFleetEmployeesPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/spend"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <RouteSuspense><LazyFleetSpendPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/notifications"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <RouteSuspense><LazyFleetNotificationsPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/incidents"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <RouteSuspense><LazyFleetIncidentsPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/incidents/:id"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <RouteSuspense><LazyFleetIncidentDetailsPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/policy-center"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <RouteSuspense><LazyFleetPolicyCenterOverviewPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/policy-center/actions"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <RouteSuspense><LazyFleetPoliciesPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/policy-center/notifications"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <RouteSuspense><LazyFleetNotificationPoliciesPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/policy-center/channels"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <RouteSuspense><LazyFleetNotificationChannelsPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/policy-center/executions"
                  element={
                    <ModuleGate module="FLEET" capability="CLIENT_CORE" title="Флот">
                      <RouteSuspense><LazyFleetPolicyExecutionsPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/logistics/fleet"
                  element={
                    <ModuleGate module="LOGISTICS" capability="LOGISTICS" title="Логистика">
                      <RouteSuspense><LazyFleetPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/logistics/trips"
                  element={
                    <ModuleGate module="LOGISTICS" capability="LOGISTICS" title="Логистика">
                      <RouteSuspense><LazyTripsPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/logistics/trips/:tripId"
                  element={
                    <ModuleGate module="LOGISTICS" capability="LOGISTICS" title="Логистика">
                      <RouteSuspense><LazyTripDetailsPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/logistics/fuel-control"
                  element={
                    <ModuleGate module="LOGISTICS" capability="LOGISTICS" title="Логистика">
                      <RouteSuspense><LazyFuelControlPage /></RouteSuspense>
                    </ModuleGate>
                  }
                />
                <Route
                  path="/stations-map"
                  element={
                    <AccessGate title="Карта станций">
                      <RouteSuspense><LazyStationsMapPage /></RouteSuspense>
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
        </ClientJourneyProvider>
      </ClientProvider>
    </AuthProvider>
  );
}
