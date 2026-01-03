import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { Layout } from "./components/Layout/Layout";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import BillingOverviewPage from "./pages/billing/BillingOverviewPage";
import BillingInvoicesPage from "./pages/billing/BillingInvoicesPage";
import BillingInvoiceDetailsPage from "./pages/billing/BillingInvoiceDetailsPage";
import BillingPaymentsPage from "./pages/billing/BillingPaymentsPage";
import BillingPaymentDetailsPage from "./pages/billing/BillingPaymentDetailsPage";
import BillingRefundsPage from "./pages/billing/BillingRefundsPage";
import BillingLinksPage from "./pages/billing/BillingLinksPage";
import { UsersPage } from "./pages/UsersPage";
import { CreateUserPage } from "./pages/CreateUserPage";
import { EditUserPage } from "./pages/EditUserPage";
import { OperationsListPage } from "./pages/OperationsListPage";
import { OperationDetailsPage } from "./pages/OperationDetailsPage";
import { RiskAnalyticsPage } from "./pages/RiskAnalyticsPage";
import { RiskRulesListPage } from "./pages/RiskRulesListPage";
import { RiskRuleDetailsPage } from "./pages/RiskRuleDetailsPage";
import { ProtectedRoute } from "./components/ProtectedRoute";
import PayoutsList from "./pages/finance/PayoutsList";
import PayoutBatchDetail from "./pages/finance/PayoutBatchDetail";
import ForbiddenPage from "./pages/ForbiddenPage";
import ExplainPage from "./pages/ExplainPage";
import ClientsPage from "./pages/crm/ClientsPage";
import ClientDetailsPage from "./pages/crm/ClientDetailsPage";
import ContractsPage from "./pages/crm/ContractsPage";
import ContractDetailsPage from "./pages/crm/ContractDetailsPage";
import CrmTariffsPage from "./pages/crm/TariffsPage";
import TariffDetailsPage from "./pages/crm/TariffDetailsPage";
import SubscriptionsPage from "./pages/crm/SubscriptionsPage";
import SubscriptionDetailsPage from "./pages/crm/SubscriptionDetailsPage";
import SubscriptionPreviewBillingPage from "./pages/crm/SubscriptionPreviewBillingPage";
import SubscriptionCfoExplainPage from "./pages/crm/SubscriptionCfoExplainPage";
import SubscriptionPlansPage from "./pages/subscriptions/SubscriptionPlansPage";
import SubscriptionPlanDetailsPage from "./pages/subscriptions/SubscriptionPlanDetailsPage";
import SubscriptionGamificationPage from "./pages/subscriptions/SubscriptionGamificationPage";
import MoneyHealthPage from "./pages/money/MoneyHealthPage";
import MoneyReplayPage from "./pages/money/MoneyReplayPage";
import InvoiceCfoExplainPage from "./pages/money/InvoiceCfoExplainPage";
import CasesListPage from "./pages/support/CasesListPage";
import CaseDetailsPage from "./pages/support/CaseDetailsPage";
import ReconciliationRunsPage from "./pages/reconciliation/ReconciliationRunsPage";
import ReconciliationRunDetailsPage from "./pages/reconciliation/ReconciliationRunDetailsPage";
import ReconciliationStatementsPage from "./pages/reconciliation/ReconciliationStatementsPage";
import FleetCardsPage from "./pages/fleet/FleetCardsPage";
import FleetGroupsPage from "./pages/fleet/FleetGroupsPage";
import FleetEmployeesPage from "./pages/fleet/FleetEmployeesPage";
import FleetLimitsPage from "./pages/fleet/FleetLimitsPage";
import FleetSpendPage from "./pages/fleet/FleetSpendPage";

export function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/" element={<Navigate to="/users" replace />} />
            <Route path="/finance" element={<Navigate to="/finance/invoices" replace />} />
            <Route path="/finance/invoices" element={<BillingInvoicesPage />} />
            <Route path="/finance/invoices/:id" element={<BillingInvoiceDetailsPage />} />
            <Route path="/finance/payments" element={<BillingPaymentsPage />} />
            <Route path="/finance/payments/:id" element={<BillingPaymentDetailsPage />} />
            <Route path="/finance/refunds" element={<BillingRefundsPage />} />
            <Route path="/finance/links" element={<BillingLinksPage />} />
            <Route path="/risk" element={<Navigate to="/analytics/risk" replace />} />
            <Route path="/policies" element={<Navigate to="/risk/rules" replace />} />
            <Route path="/marketplace" element={<Navigate to="/crm/clients" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/billing" element={<BillingOverviewPage />}>
              <Route index element={<Navigate to="/billing/invoices" replace />} />
              <Route path="invoices" element={<BillingInvoicesPage />} />
              <Route path="payments" element={<BillingPaymentsPage />} />
              <Route path="refunds" element={<BillingRefundsPage />} />
              <Route path="links" element={<BillingLinksPage />} />
            </Route>
            <Route path="/billing/invoices/:id" element={<BillingInvoiceDetailsPage />} />
            <Route path="/billing/payments/:id" element={<BillingPaymentDetailsPage />} />
            <Route path="/users" element={<UsersPage />} />
            <Route path="/users/new" element={<CreateUserPage />} />
            <Route path="/users/:id" element={<EditUserPage />} />
            <Route path="/operations" element={<OperationsListPage />} />
            <Route path="/operations/:id" element={<OperationDetailsPage />} />
            <Route path="/analytics/risk" element={<RiskAnalyticsPage />} />
            <Route path="/risk/rules" element={<RiskRulesListPage />} />
            <Route path="/risk/rules/:id" element={<RiskRuleDetailsPage />} />
            <Route path="/finance/payouts" element={<PayoutsList />} />
            <Route path="/finance/payouts/:batchId" element={<PayoutBatchDetail />} />
            <Route path="/forbidden" element={<ForbiddenPage />} />
            <Route path="/explain" element={<ExplainPage />} />
            <Route path="/crm/clients" element={<ClientsPage />} />
            <Route path="/crm/clients/:id" element={<ClientDetailsPage />} />
            <Route path="/crm/contracts" element={<ContractsPage />} />
            <Route path="/crm/contracts/:id" element={<ContractDetailsPage />} />
            <Route path="/crm/tariffs" element={<CrmTariffsPage />} />
            <Route path="/crm/tariffs/:id" element={<TariffDetailsPage />} />
            <Route path="/crm/subscriptions" element={<SubscriptionsPage />} />
            <Route path="/crm/subscriptions/:id" element={<SubscriptionDetailsPage />} />
            <Route path="/crm/subscriptions/:id/preview-billing" element={<SubscriptionPreviewBillingPage />} />
            <Route path="/crm/subscriptions/:id/cfo-explain" element={<SubscriptionCfoExplainPage />} />
            <Route path="/subscriptions/plans" element={<SubscriptionPlansPage />} />
            <Route path="/subscriptions/plans/:id" element={<SubscriptionPlanDetailsPage />} />
            <Route path="/subscriptions/gamification" element={<SubscriptionGamificationPage />} />
            <Route path="/money/health" element={<MoneyHealthPage />} />
            <Route path="/money/replay" element={<MoneyReplayPage />} />
            <Route path="/money/invoices/:id/cfo-explain" element={<InvoiceCfoExplainPage />} />
            <Route path="/support/cases" element={<CasesListPage />} />
            <Route path="/support/cases/:id" element={<CaseDetailsPage />} />
            <Route path="/reconciliation" element={<ReconciliationRunsPage />} />
            <Route path="/reconciliation/runs/:id" element={<ReconciliationRunDetailsPage />} />
            <Route path="/reconciliation/statements" element={<ReconciliationStatementsPage />} />
            <Route path="/fleet/cards" element={<FleetCardsPage />} />
            <Route path="/fleet/groups" element={<FleetGroupsPage />} />
            <Route path="/fleet/employees" element={<FleetEmployeesPage />} />
            <Route path="/fleet/limits" element={<FleetLimitsPage />} />
            <Route path="/fleet/spend" element={<FleetSpendPage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </AuthProvider>
  );
}

export default App;
