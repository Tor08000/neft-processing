import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import type { AuthSession } from "./api/types";
import { Layout } from "./components/Layout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { DashboardPage } from "./pages/DashboardPage";
import { OperationsPage } from "./pages/OperationsPage";
import { OperationDetailsPage } from "./pages/OperationDetailsPage";
import { ClientCardsPage } from "./pages/ClientCardsPage";
import { ClientCardDetailsPage } from "./pages/ClientCardDetailsPage";
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
import { ExplainPage } from "./pages/ExplainPage";
import { ExplainInsightsPage } from "./pages/ExplainInsightsPage";
import { ActionsPage } from "./pages/ActionsPage";
import { useAuth } from "./auth/AuthContext";
import { SettingsPage } from "./pages/SettingsPage";
import { ClientControlsPage } from "./pages/ClientControlsPage";
import { MarketplaceCatalogPage } from "./pages/MarketplaceCatalogPage";
import { MarketplaceServicePage } from "./pages/MarketplaceServicePage";
import { MarketplaceOrdersPage } from "./pages/MarketplaceOrdersPage";
import { MarketplaceOrderDetailsPage } from "./pages/MarketplaceOrderDetailsPage";
import { SupportRequestsPage } from "./pages/SupportRequestsPage";
import { SupportRequestDetailsPage } from "./pages/SupportRequestDetailsPage";
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
import { isPwaMode } from "./pwa/mode";

interface AppProps {
  initialSession?: AuthSession | null;
}

function IndexRedirect() {
  const { user } = useAuth();
  if (user) {
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
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout pwaMode={isPwaMode} />}>
            {isPwaMode ? (
              <>
                <Route index element={<PwaIndexRedirect />} />
                <Route path="/marketplace/orders" element={<MarketplaceOrdersPage />} />
                <Route path="/marketplace/orders/:orderId" element={<MarketplaceOrderDetailsPage />} />
                <Route path="/documents" element={<ClientDocumentsPage />} />
                <Route path="/documents/:id" element={<ClientDocumentDetailsPage />} />
              </>
            ) : (
              <>
                <Route index element={<IndexRedirect />} />
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/analytics" element={<AnalyticsDashboardPage />} />
                <Route path="/analytics/spend" element={<AnalyticsSpendPage />} />
                <Route path="/analytics/declines" element={<AnalyticsDeclinesPage />} />
                <Route path="/analytics/marketplace" element={<AnalyticsMarketplacePage />} />
                <Route path="/analytics/documents" element={<AnalyticsDocumentsPage />} />
                <Route path="/analytics/exports" element={<AnalyticsExportsPage />} />
                <Route path="/spend/transactions" element={<OperationsPage />} />
                <Route path="/explain" element={<ExplainPage />} />
                <Route path="/explain/insights" element={<ExplainInsightsPage />} />
                <Route path="/explain/:id" element={<ExplainPage />} />
                <Route path="/documents" element={<ClientDocumentsPage />} />
                <Route path="/documents/:id" element={<ClientDocumentDetailsPage />} />
                <Route path="/exports" element={<FinanceExportsPage />} />
                <Route path="/exports/:id" element={<FinanceExportDetailsPage />} />
                <Route path="/actions" element={<ActionsPage />} />
                <Route path="/cards" element={<ClientCardsPage />} />
                <Route path="/cards/:id" element={<ClientCardDetailsPage />} />
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
                <Route path="/finance/reconciliation" element={<ReconciliationRequestsPage />} />
                <Route path="/finance/exports" element={<FinanceExportsPage />} />
                <Route path="/operations" element={<OperationsPage />} />
                <Route path="/operations/:id" element={<OperationDetailsPage />} />
                <Route path="/balances" element={<BalancesPage />} />
                <Route path="/marketplace" element={<MarketplaceCatalogPage />} />
                <Route path="/marketplace/orders" element={<MarketplaceOrdersPage />} />
                <Route path="/marketplace/orders/:orderId" element={<MarketplaceOrderDetailsPage />} />
                <Route path="/marketplace/:serviceId" element={<MarketplaceServicePage />} />
                <Route path="/support/requests" element={<SupportRequestsPage />} />
                <Route path="/support/requests/:id" element={<SupportRequestDetailsPage />} />
                <Route path="/cases" element={<CasesPage />} />
                <Route path="/cases/:id" element={<CaseDetailsPage />} />
                <Route path="/subscription" element={<SubscriptionPage />} />
                <Route path="/profile" element={<ProfilePage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/settings/management" element={<ClientControlsPage />} />
                <Route path="/fleet/cards" element={<FleetCardsPage />} />
                <Route path="/fleet/cards/:id" element={<FleetCardDetailsPage />} />
                <Route path="/fleet/groups" element={<FleetGroupsPage />} />
                <Route path="/fleet/groups/:id" element={<FleetGroupDetailsPage />} />
                <Route path="/fleet/employees" element={<FleetEmployeesPage />} />
                <Route path="/fleet/spend" element={<FleetSpendPage />} />
                <Route path="/fleet/notifications" element={<FleetNotificationsPage />} />
                <Route path="/fleet/policy-center" element={<FleetPolicyCenterOverviewPage />} />
                <Route path="/fleet/policy-center/actions" element={<FleetPoliciesPage />} />
                <Route path="/fleet/policy-center/notifications" element={<FleetNotificationPoliciesPage />} />
                <Route path="/fleet/policy-center/channels" element={<FleetNotificationChannelsPage />} />
                <Route path="/fleet/policy-center/executions" element={<FleetPolicyExecutionsPage />} />
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
    </AuthProvider>
  );
}
