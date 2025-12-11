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
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </AuthProvider>
  );
}

export default App;
