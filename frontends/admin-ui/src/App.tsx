import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { LegalGateProvider } from "./auth/LegalGateContext";
import { LoginPage } from "./pages/LoginPage";
import { AdminProvider } from "./admin/AdminContext";
import { AdminAuthGuard } from "./admin/AdminAuthGuard";
import { AdminErrorBoundary } from "./admin/AdminErrorBoundary";
import { AdminShell } from "./admin/AdminShell";
import { AdminRBACGate } from "./admin/AdminRBACGate";
import AdminDashboardPage from "./pages/admin/AdminDashboardPage";
import { AdminNotFoundPage } from "./pages/admin/AdminStatusPages";
import OpsOverviewPage from "./pages/ops/OpsOverviewPage";
import OpsBlockedPayoutsPage from "./pages/ops/OpsBlockedPayoutsPage";
import OpsFailedExportsPage from "./pages/ops/OpsFailedExportsPage";
import OpsFailedImportsPage from "./pages/ops/OpsFailedImportsPage";
import OpsSupportBreachesPage from "./pages/ops/OpsSupportBreachesPage";
import RuntimeCenterPage from "./pages/admin/RuntimeCenterPage";
import CommercialOrgPage from "./pages/admin/CommercialOrgPage";
import FinanceOverviewPage from "./pages/finance/FinanceOverviewPage";
import InvoicesPage from "./pages/finance/InvoicesPage";
import InvoiceDetailsPage from "./pages/finance/InvoiceDetailsPage";
import PaymentIntakesPage from "./pages/finance/PaymentIntakesPage";
import ReconciliationImportsPage from "./pages/finance/ReconciliationImportsPage";
import ReconciliationImportDetailsPage from "./pages/finance/ReconciliationImportDetailsPage";
import PayoutQueuePage from "./pages/finance/PayoutQueuePage";
import PayoutDetailsPage from "./pages/finance/PayoutDetailsPage";
import RevenuePage from "./pages/finance/RevenuePage";
import LegalPage from "./pages/legal/LegalPage";
import LegalPartnersPage from "./pages/legal/LegalPartnersPage";
import AuditPage from "./pages/admin/AuditPage";
import MarketplaceModerationPage from "./pages/marketplace/MarketplaceModerationPage";
import GeoAnalyticsPage from "./pages/GeoAnalyticsPage";
import RulesSandboxPage from "./pages/RulesSandboxPage";
import RiskRulesListPage from "./pages/RiskRulesListPage";
import RiskRuleDetailsPage from "./pages/RiskRuleDetailsPage";
import PolicyCenterPage from "./pages/PolicyCenterPage";
import PolicyCenterDetailPage from "./pages/PolicyCenterDetailPage";
import InvitationsPage from "./pages/admin/InvitationsPage";
import CasesListPage from "./pages/cases/CasesListPage";
import CaseDetailsPage from "./pages/cases/CaseDetailsPage";
import UsersPage from "./pages/UsersPage";
import CreateUserPage from "./pages/CreateUserPage";
import EditUserPage from "./pages/EditUserPage";
import ClientsPage from "./pages/crm/ClientsPage";
import ClientDetailsPage from "./pages/crm/ClientDetailsPage";
import ContractsPage from "./pages/crm/ContractsPage";
import ContractDetailsPage from "./pages/crm/ContractDetailsPage";
import TariffsPage from "./pages/crm/TariffsPage";
import TariffDetailsPage from "./pages/crm/TariffDetailsPage";
import SubscriptionsPage from "./pages/crm/SubscriptionsPage";
import SubscriptionDetailsPage from "./pages/crm/SubscriptionDetailsPage";
import SubscriptionPreviewBillingPage from "./pages/crm/SubscriptionPreviewBillingPage";
import SubscriptionCfoExplainPage from "./pages/crm/SubscriptionCfoExplainPage";
import LogisticsInspectionPage from "./pages/logistics/LogisticsInspectionPage";
import EscalationsPage from "./pages/ops/EscalationsPage";
import KpiPage from "./pages/ops/KpiPage";
import {
  MarketplaceModerationOfferDetailPage,
  MarketplaceModerationProductDetailPage,
  MarketplaceModerationServiceDetailPage,
} from "./pages/marketplace/MarketplaceModerationDetailPage";

export function App() {
  const location = useLocation();

  return (
    <AuthProvider>
      <LegalGateProvider>
        <AdminProvider>
          <AdminErrorBoundary resetKey={location.pathname}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route element={<AdminAuthGuard />}>
                <Route element={<AdminShell />}>
                  <Route path="/" element={<AdminDashboardPage />} />
                  <Route
                    path="/admins"
                    element={
                      <AdminRBACGate permission="access">
                        <UsersPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/admins/new"
                    element={
                      <AdminRBACGate permission="access" action="manage">
                        <CreateUserPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/admins/:id"
                    element={
                      <AdminRBACGate permission="access" action="manage">
                        <EditUserPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/ops"
                    element={
                      <AdminRBACGate permission="ops">
                        <OpsOverviewPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/runtime"
                    element={
                      <AdminRBACGate permission="runtime">
                        <RuntimeCenterPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/ops/payouts/blocked"
                    element={
                      <AdminRBACGate permission="ops">
                        <OpsBlockedPayoutsPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/ops/exports/failed"
                    element={
                      <AdminRBACGate permission="ops">
                        <OpsFailedExportsPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/ops/reconciliation/failed"
                    element={
                      <AdminRBACGate permission="ops">
                        <OpsFailedImportsPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/ops/support/breaches"
                    element={
                      <AdminRBACGate permission="ops">
                        <OpsSupportBreachesPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/ops/escalations"
                    element={
                      <AdminRBACGate permission="ops">
                        <EscalationsPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/ops/kpi"
                    element={
                      <AdminRBACGate permission="ops">
                        <KpiPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/logistics/inspection"
                    element={
                      <AdminRBACGate permission="ops">
                        <LogisticsInspectionPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/finance"
                    element={
                      <AdminRBACGate permission="finance">
                        <FinanceOverviewPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/finance/invoices"
                    element={
                      <AdminRBACGate permission="finance">
                        <InvoicesPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/finance/invoices/:invoiceId"
                    element={
                      <AdminRBACGate permission="finance">
                        <InvoiceDetailsPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/finance/payment-intakes"
                    element={
                      <AdminRBACGate permission="finance">
                        <PaymentIntakesPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/finance/reconciliation/imports"
                    element={
                      <AdminRBACGate permission="finance">
                        <ReconciliationImportsPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/finance/reconciliation/imports/:importId"
                    element={
                      <AdminRBACGate permission="finance">
                        <ReconciliationImportDetailsPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/finance/payouts"
                    element={
                      <AdminRBACGate permission="finance">
                        <PayoutQueuePage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/finance/payouts/:payoutId"
                    element={
                      <AdminRBACGate permission="finance">
                        <PayoutDetailsPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/finance/revenue"
                    element={
                      <AdminRBACGate permission="revenue">
                        <RevenuePage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/geo"
                    element={
                      <AdminRBACGate permission="ops">
                        <GeoAnalyticsPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/rules/sandbox"
                    element={
                      <AdminRBACGate permission="ops">
                        <RulesSandboxPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/risk/rules"
                    element={
                      <AdminRBACGate permission="ops">
                        <RiskRulesListPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/risk/rules/:id"
                    element={
                      <AdminRBACGate permission="ops">
                        <RiskRuleDetailsPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/policies"
                    element={
                      <AdminRBACGate permission="ops">
                        <PolicyCenterPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/policies/:type/:id"
                    element={
                      <AdminRBACGate permission="ops">
                        <PolicyCenterDetailPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/invitations"
                    element={
                      <AdminRBACGate permission="onboarding">
                        <InvitationsPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/cases"
                    element={
                      <AdminRBACGate permission="cases">
                        <CasesListPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/cases/:id"
                    element={
                      <AdminRBACGate permission="cases">
                        <CaseDetailsPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/commercial"
                    element={
                      <AdminRBACGate permission="commercial">
                        <CommercialOrgPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/commercial/:orgId"
                    element={
                      <AdminRBACGate permission="commercial">
                        <CommercialOrgPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/sales"
                    element={
                      <AdminRBACGate permission="crm">
                        <Navigate to="/crm/clients" replace />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/crm"
                    element={
                      <AdminRBACGate permission="crm">
                        <Navigate to="/crm/clients" replace />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/crm/clients"
                    element={
                      <AdminRBACGate permission="crm">
                        <ClientsPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/crm/clients/:id"
                    element={
                      <AdminRBACGate permission="crm">
                        <ClientDetailsPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/crm/contracts"
                    element={
                      <AdminRBACGate permission="crm">
                        <ContractsPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/crm/contracts/:id"
                    element={
                      <AdminRBACGate permission="crm">
                        <ContractDetailsPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/crm/tariffs"
                    element={
                      <AdminRBACGate permission="crm">
                        <TariffsPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/crm/tariffs/:id"
                    element={
                      <AdminRBACGate permission="crm">
                        <TariffDetailsPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/crm/subscriptions"
                    element={
                      <AdminRBACGate permission="crm">
                        <SubscriptionsPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/crm/subscriptions/:id"
                    element={
                      <AdminRBACGate permission="crm">
                        <SubscriptionDetailsPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/crm/subscriptions/:id/preview-billing"
                    element={
                      <AdminRBACGate permission="crm">
                        <SubscriptionPreviewBillingPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/crm/subscriptions/:id/cfo-explain"
                    element={
                      <AdminRBACGate permission="crm">
                        <SubscriptionCfoExplainPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/legal"
                    element={
                      <AdminRBACGate permission="legal">
                        <Navigate to="/legal/documents" replace />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/legal/documents"
                    element={
                      <AdminRBACGate permission="legal">
                        <LegalPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/legal/partners"
                    element={
                      <AdminRBACGate permission="legal">
                        <LegalPartnersPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/audit"
                    element={
                      <AdminRBACGate permission="audit">
                        <AuditPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/audit/:correlationId"
                    element={
                      <AdminRBACGate permission="audit">
                        <AuditPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/marketplace"
                    element={
                      <AdminRBACGate permission="marketplace">
                        <Navigate to="/marketplace/moderation" replace />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/marketplace/moderation"
                    element={
                      <AdminRBACGate permission="marketplace">
                        <MarketplaceModerationPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/marketplace/moderation/product/:id"
                    element={
                      <AdminRBACGate permission="marketplace">
                        <MarketplaceModerationProductDetailPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/marketplace/moderation/service/:id"
                    element={
                      <AdminRBACGate permission="marketplace">
                        <MarketplaceModerationServiceDetailPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/marketplace/moderation/offer/:id"
                    element={
                      <AdminRBACGate permission="marketplace">
                        <MarketplaceModerationOfferDetailPage />
                      </AdminRBACGate>
                    }
                  />
                  <Route path="*" element={<AdminNotFoundPage />} />
                </Route>
              </Route>
              <Route path="*" element={<AdminNotFoundPage />} />
            </Routes>
          </AdminErrorBoundary>
        </AdminProvider>
      </LegalGateProvider>
    </AuthProvider>
  );
}

export default App;
