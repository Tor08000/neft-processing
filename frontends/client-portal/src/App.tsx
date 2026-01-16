import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { ClientProvider, useClient } from "./auth/ClientContext";
import { LegalGateProvider } from "./auth/LegalGateContext";
import type { AuthSession } from "./api/types";
import { Layout } from "./components/Layout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { ModuleGate } from "./components/ModuleGate";
import { LoginPage } from "./pages/LoginPage";
import { SignupPage } from "./pages/SignupPage";
import { OnboardingPage } from "./pages/OnboardingPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { UnauthorizedPage } from "./pages/UnauthorizedPage";
import { DashboardPage } from "./pages/DashboardPage";
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
import { ClientDocumentDetailsPage } from "./pages/ClientDocumentDetailsPage";
import { ClientDocsListPage } from "./pages/ClientDocsListPage";
import { ExplainPage } from "./pages/ExplainPage";
import { ExplainInsightsPage } from "./pages/ExplainInsightsPage";
import { ActionsPage } from "./pages/ActionsPage";
import { useAuth } from "./auth/AuthContext";
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
import { AuditPage } from "./pages/AuditPage";
import { isPwaMode } from "./pwa/mode";
import { LegalPage } from "./pages/LegalPage";
import { ReportsPage } from "./pages/ReportsPage";
import { ExportsPage } from "./pages/ExportsPage";

interface AppProps {
  initialSession?: AuthSession | null;
}

function IndexRedirect() {
  const { user } = useAuth();
  const { client } = useClient();
  if (user) {
    if (!client?.org || client.org_status !== "ACTIVE") {
      return <Navigate to="/client/connect" replace />;
    }
    return <Navigate to="/dashboard" replace />;
  }
  return <Navigate to="/login" replace />;
}

function PwaIndexRedirect() {
  const { user } = useAuth();
  if (user) {
    return <Navigate to="/marketplace/orders" replace />;
  }
  return <Navigate to="/login" replace />;
}

export function App({ initialSession = null }: AppProps) {
  return (
    <AuthProvider initialSession={initialSession}>
      <ClientProvider>
        <LegalGateProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/client/signup" element={<SignupPage />} />
            <Route path="/unauthorized" element={<UnauthorizedPage />} />
            <Route element={<ProtectedRoute />}>
              <Route path="/client/connect" element={<OnboardingPage />} />
              <Route path="/client/onboarding" element={<OnboardingPage />} />
              <Route element={<Layout pwaMode={isPwaMode} />}>
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
                  <Route path="/dashboard" element={<DashboardPage />} />
                <Route
                  path="/vehicles"
                  element={
                    <ModuleGate module="FLEET" title="Флот">
                      <FleetGroupsPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/vehicles/:id"
                  element={
                    <ModuleGate module="FLEET" title="Флот">
                      <FleetGroupDetailsPage />
                    </ModuleGate>
                  }
                />
                <Route path="/cards" element={<ClientCardsPage />} />
                <Route path="/limits/templates" element={<LimitTemplatesPage />} />
                <Route path="/cards/:id" element={<ClientCardDetailsPage />} />
                <Route path="/cards/:id/limits" element={<ClientCardDetailsPage />} />
                <Route path="/cards/:id/access" element={<ClientCardDetailsPage />} />
                <Route
                  path="/orders"
                  element={
                    <ModuleGate module="MARKETPLACE" title="Маркетплейс">
                      <MarketplaceOrdersPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/orders/:orderId"
                  element={
                    <ModuleGate module="MARKETPLACE" title="Маркетплейс">
                      <MarketplaceOrderDetailsPage />
                    </ModuleGate>
                  }
                />
                <Route path="/billing" element={<ClientInvoicesPage />} />
                <Route path="/billing/:id" element={<ClientInvoiceDetailsPage />} />
                <Route path="/client/support" element={<SupportTicketsPage />} />
                <Route path="/client/support/new" element={<SupportTicketNewPage />} />
                <Route path="/client/support/:id" element={<SupportTicketDetailsPage />} />
                <Route path="/support" element={<Navigate to="/client/support" replace />} />
                <Route path="/support/:id" element={<SupportTicketDetailsPage />} />
                <Route
                  path="/analytics"
                  element={
                    <ModuleGate module="ANALYTICS" title="Аналитика">
                      <AnalyticsDashboardPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/analytics/spend"
                  element={
                    <ModuleGate module="ANALYTICS" title="Аналитика">
                      <AnalyticsSpendPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/analytics/declines"
                  element={
                    <ModuleGate module="ANALYTICS" title="Аналитика">
                      <AnalyticsDeclinesPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/analytics/marketplace"
                  element={
                    <ModuleGate module="ANALYTICS" title="Аналитика">
                      <AnalyticsMarketplacePage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/analytics/documents"
                  element={
                    <ModuleGate module="ANALYTICS" title="Аналитика">
                      <AnalyticsDocumentsPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/analytics/exports"
                  element={
                    <ModuleGate module="ANALYTICS" title="Аналитика">
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
                <Route path="/client/documents" element={<ClientDocumentsPage />} />
                <Route path="/client/documents/:id" element={<ClientDocumentDetailsPage />} />
                <Route
                  path="/client/docs/contracts"
                  element={<ClientDocsListPage title="Договоры" docType="CONTRACT" />}
                />
                <Route
                  path="/client/docs/invoices"
                  element={<ClientDocsListPage title="Счета" docType="INVOICE" />}
                />
                <Route
                  path="/client/docs/acts"
                  element={<ClientDocsListPage title="Акты" docType="ACT" />}
                />
                <Route path="/finance/reconciliation" element={<ReconciliationRequestsPage />} />
                <Route path="/finance/exports" element={<FinanceExportsPage />} />
                <Route path="/operations" element={<OperationsPage />} />
                <Route path="/operations/:id" element={<OperationDetailsPage />} />
                <Route path="/balances" element={<BalancesPage />} />
                <Route
                  path="/marketplace"
                  element={
                    <ModuleGate module="MARKETPLACE" title="Маркетплейс">
                      <MarketplaceCatalogPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/marketplace/products/:productId"
                  element={
                    <ModuleGate module="MARKETPLACE" title="Маркетплейс">
                      <MarketplaceProductDetailsPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/marketplace/orders"
                  element={
                    <ModuleGate module="MARKETPLACE" title="Маркетплейс">
                      <MarketplaceOrdersPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/marketplace/orders/:orderId"
                  element={
                    <ModuleGate module="MARKETPLACE" title="Маркетплейс">
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
                <Route path="/settings/management" element={<ClientControlsPage />} />
                <Route path="/audit" element={<AuditPage />} />
                <Route path="/client/reports" element={<ReportsPage />} />
                <Route path="/client/exports" element={<ExportsPage />} />
                <Route path="/legal" element={<LegalPage />} />
                <Route
                  path="/fleet/cards"
                  element={
                    <ModuleGate module="FLEET" title="Флот">
                      <FleetCardsPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/cards/:id"
                  element={
                    <ModuleGate module="FLEET" title="Флот">
                      <FleetCardDetailsPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/groups"
                  element={
                    <ModuleGate module="FLEET" title="Флот">
                      <FleetGroupsPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/groups/:id"
                  element={
                    <ModuleGate module="FLEET" title="Флот">
                      <FleetGroupDetailsPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/employees"
                  element={
                    <ModuleGate module="FLEET" title="Флот">
                      <FleetEmployeesPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/spend"
                  element={
                    <ModuleGate module="FLEET" title="Флот">
                      <FleetSpendPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/notifications"
                  element={
                    <ModuleGate module="FLEET" title="Флот">
                      <FleetNotificationsPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/incidents"
                  element={
                    <ModuleGate module="FLEET" title="Флот">
                      <FleetIncidentsPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/incidents/:id"
                  element={
                    <ModuleGate module="FLEET" title="Флот">
                      <FleetIncidentDetailsPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/policy-center"
                  element={
                    <ModuleGate module="FLEET" title="Флот">
                      <FleetPolicyCenterOverviewPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/policy-center/actions"
                  element={
                    <ModuleGate module="FLEET" title="Флот">
                      <FleetPoliciesPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/policy-center/notifications"
                  element={
                    <ModuleGate module="FLEET" title="Флот">
                      <FleetNotificationPoliciesPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/policy-center/channels"
                  element={
                    <ModuleGate module="FLEET" title="Флот">
                      <FleetNotificationChannelsPage />
                    </ModuleGate>
                  }
                />
                <Route
                  path="/fleet/policy-center/executions"
                  element={
                    <ModuleGate module="FLEET" title="Флот">
                      <FleetPolicyExecutionsPage />
                    </ModuleGate>
                  }
                />
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
