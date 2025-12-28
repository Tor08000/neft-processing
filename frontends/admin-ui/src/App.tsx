import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { Layout } from "./components/Layout/Layout";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import BillingDashboardPage from "./pages/BillingDashboardPage";
import TariffsPage from "./pages/TariffsPage";
import InvoicesListPage from "./pages/InvoicesListPage";
import InvoiceDetailsPage from "./pages/InvoiceDetailsPage";
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
import MoneyHealthPage from "./pages/money/MoneyHealthPage";
import MoneyReplayPage from "./pages/money/MoneyReplayPage";
import InvoiceCfoExplainPage from "./pages/money/InvoiceCfoExplainPage";

export function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/" element={<Navigate to="/users" replace />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/billing" element={<BillingDashboardPage />} />
            <Route path="/billing/tariffs" element={<TariffsPage />} />
            <Route path="/billing/invoices" element={<InvoicesListPage />} />
            <Route path="/billing/invoices/:id" element={<InvoiceDetailsPage />} />
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
            <Route path="/money/health" element={<MoneyHealthPage />} />
            <Route path="/money/replay" element={<MoneyReplayPage />} />
            <Route path="/money/invoices/:id/cfo-explain" element={<InvoiceCfoExplainPage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </AuthProvider>
  );
}

export default App;
