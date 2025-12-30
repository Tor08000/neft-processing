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
import { FinanceExportsPage } from "./pages/FinanceExportsPage";
import { ReconciliationRequestsPage } from "./pages/ReconciliationRequestsPage";
import { ClientDocumentsPage } from "./pages/ClientDocumentsPage";
import { ClientDocumentDetailsPage } from "./pages/ClientDocumentDetailsPage";
import { ExplainPage } from "./pages/ExplainPage";
import { ActionsPage } from "./pages/ActionsPage";
import { useAuth } from "./auth/AuthContext";

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

export function App({ initialSession = null }: AppProps) {
  return (
    <AuthProvider initialSession={initialSession}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route index element={<IndexRedirect />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/spend/transactions" element={<OperationsPage />} />
            <Route path="/explain" element={<ExplainPage />} />
            <Route path="/explain/:id" element={<ExplainPage />} />
            <Route path="/documents" element={<ClientDocumentsPage />} />
            <Route path="/documents/:id" element={<ClientDocumentDetailsPage />} />
            <Route path="/exports" element={<FinanceExportsPage />} />
            <Route path="/actions" element={<ActionsPage />} />
            <Route path="/cards" element={<ClientCardsPage />} />
            <Route path="/cards/:id" element={<ClientCardDetailsPage />} />
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
            <Route path="/profile" element={<ProfilePage />} />
          </Route>
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AuthProvider>
  );
}
