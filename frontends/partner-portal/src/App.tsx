import { Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import type { AuthSession } from "./api/types";
import { Layout } from "./components/Layout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { DashboardPage } from "./pages/DashboardPage";
import { StationsPage } from "./pages/StationsPage";
import { StationDetailsPage } from "./pages/StationDetailsPage";
import { TransactionsPage } from "./pages/TransactionsPage";
import { TransactionDetailsPage } from "./pages/TransactionDetailsPage";
import { PayoutsPage } from "./pages/PayoutsPage";
import { SettlementDetailsPage } from "./pages/SettlementDetailsPage";
import { PayoutBatchesPage } from "./pages/PayoutBatchesPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { DocumentDetailsPage } from "./pages/DocumentDetailsPage";
import { OrdersPage } from "./pages/OrdersPage";
import { OrderDetailsPage } from "./pages/OrderDetailsPage";
import { RefundsPage } from "./pages/RefundsPage";
import { RefundDetailsPage } from "./pages/RefundDetailsPage";
import { ServicesCatalogPage } from "./pages/ServicesCatalogPage";
import { ServiceDetailsPage } from "./pages/ServiceDetailsPage";
import { PricesPage } from "./pages/PricesPage";
import { PriceAnalyticsPage } from "./pages/PriceAnalyticsPage";
import { PriceVersionDetailsPage } from "./pages/PriceVersionDetailsPage";
import { IntegrationsPage } from "./pages/IntegrationsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SupportRequestsPage } from "./pages/SupportRequestsPage";
import { SupportRequestDetailsPage } from "./pages/SupportRequestDetailsPage";

interface AppProps {
  initialSession?: AuthSession | null;
}

export function App({ initialSession = null }: AppProps) {
  return (
    <AuthProvider initialSession={initialSession}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route index element={<DashboardPage />} />
            <Route path="/stations" element={<StationsPage />} />
            <Route path="/stations/:id" element={<StationDetailsPage />} />
            <Route path="/transactions" element={<TransactionsPage />} />
            <Route path="/transactions/:id" element={<TransactionDetailsPage />} />
            <Route path="/prices" element={<PricesPage />} />
            <Route path="/prices/analytics" element={<PriceAnalyticsPage />} />
            <Route path="/prices/:id" element={<PriceVersionDetailsPage />} />
            <Route path="/payouts" element={<PayoutsPage />} />
            <Route path="/payouts/:id" element={<SettlementDetailsPage />} />
            <Route path="/payouts/batches" element={<PayoutBatchesPage />} />
            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="/documents/:id" element={<DocumentDetailsPage />} />
            <Route path="/orders" element={<OrdersPage />} />
            <Route path="/orders/:id" element={<OrderDetailsPage />} />
            <Route path="/refunds" element={<RefundsPage />} />
            <Route path="/refunds/:id" element={<RefundDetailsPage />} />
            <Route path="/services" element={<ServicesCatalogPage />} />
            <Route path="/services/:id" element={<ServiceDetailsPage />} />
            <Route path="/integrations" element={<IntegrationsPage />} />
            <Route path="/support/requests" element={<SupportRequestsPage />} />
            <Route path="/support/requests/:id" element={<SupportRequestDetailsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </AuthProvider>
  );
}
