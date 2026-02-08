import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { PortalProvider } from "./auth/PortalContext";
import { LegalGateProvider } from "./auth/LegalGateContext";
import type { AuthSession } from "./api/types";
import { Layout } from "./components/Layout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AccessGate } from "./components/AccessGate";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { DashboardPage } from "./pages/DashboardPage";
import { StationsPage } from "./pages/StationsPage";
import { StationDetailsPage } from "./pages/StationDetailsPage";
import { TransactionsPage } from "./pages/TransactionsPage";
import { TransactionDetailsPage } from "./pages/TransactionDetailsPage";
import { PartnerContractsPage } from "./pages/PartnerContractsPage";
import { PayoutsPage } from "./pages/payouts/PayoutsPage";
import { SettlementDetailsPage } from "./pages/SettlementDetailsPage";
import { PayoutBatchesPage } from "./pages/PayoutBatchesPage";
import { PayoutTracePage } from "./pages/PayoutTracePage";
import { DocumentsPage } from "./pages/documents/DocumentsPage";
import { DocumentDetailsPage } from "./pages/DocumentDetailsPage";
import { FinancePage } from "./pages/finance/FinancePage";
import { OrdersPage } from "./pages/orders/OrdersPage";
import { OrderDetailsPage } from "./pages/OrderDetailsPage";
import { RefundsPage } from "./pages/RefundsPage";
import { RefundDetailsPage } from "./pages/RefundDetailsPage";
import { ServicesCatalogPage } from "./pages/services/ServicesCatalogPage";
import { ServiceDetailsPage } from "./pages/ServiceDetailsPage";
import { PricesPage } from "./pages/PricesPage";
import { AnalyticsPage } from "./pages/analytics/AnalyticsPage";
import { PriceVersionDetailsPage } from "./pages/PriceVersionDetailsPage";
import { IntegrationsPage } from "./pages/IntegrationsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SupportRequestsPage } from "./pages/SupportRequestsPage";
import { SupportRequestDetailsPage } from "./pages/SupportRequestDetailsPage";
import { MarketplaceProfilePage } from "./pages/MarketplaceProfilePage";
import { MarketplaceProductsPage } from "./pages/MarketplaceProductsPage";
import { MarketplaceOffersPage } from "./pages/MarketplaceOffersPage";
import { LegalPage } from "./pages/LegalPage";

interface AppProps {
  initialSession?: AuthSession | null;
}

export function App({ initialSession = null }: AppProps) {
  return (
    <AuthProvider initialSession={initialSession}>
      <PortalProvider>
        <LegalGateProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<ProtectedRoute />}>
              <Route element={<Layout />}>
                <Route index element={<Navigate to="/products" replace />} />
                <Route
                  path="/dashboard"
                  element={
                    <AccessGate title="Дашборд">
                      <DashboardPage />
                    </AccessGate>
                  }
                />
                <Route path="/products" element={<MarketplaceProductsPage />} />
                <Route path="/products/:id" element={<MarketplaceProductsPage />} />
                <Route path="/bookings" element={<ServicesCatalogPage />} />
                <Route path="/bookings/:id" element={<ServiceDetailsPage />} />
                <Route path="/promotions" element={<MarketplaceProfilePage />} />
                <Route path="/analytics" element={<AnalyticsPage />} />
                <Route path="/contracts" element={<PartnerContractsPage />} />
                <Route path="/stations" element={<StationsPage />} />
                <Route path="/stations/:id" element={<StationDetailsPage />} />
                <Route path="/transactions" element={<TransactionsPage />} />
                <Route path="/transactions/:id" element={<TransactionDetailsPage />} />
                <Route path="/prices" element={<PricesPage />} />
                <Route path="/prices/analytics" element={<AnalyticsPage />} />
                <Route path="/prices/:id" element={<PriceVersionDetailsPage />} />
                <Route
                  path="/finance"
                  element={
                    <AccessGate title="Финансы">
                      <FinancePage />
                    </AccessGate>
                  }
                />
                <Route
                  path="/payouts"
                  element={
                    <AccessGate title="Выплаты">
                      <PayoutsPage />
                    </AccessGate>
                  }
                />
                <Route
                  path="/payouts/:id"
                  element={
                    <AccessGate title="Выплаты">
                      <SettlementDetailsPage />
                    </AccessGate>
                  }
                />
                <Route path="/payouts/batches" element={<PayoutBatchesPage />} />
                <Route path="/payouts/batches/:id" element={<PayoutTracePage />} />
                <Route
                  path="/documents"
                  element={
                    <AccessGate title="Документы">
                      <DocumentsPage />
                    </AccessGate>
                  }
                />
                <Route
                  path="/documents/:id"
                  element={
                    <AccessGate title="Документы">
                      <DocumentDetailsPage />
                    </AccessGate>
                  }
                />
                <Route path="/orders" element={<OrdersPage />} />
                <Route path="/orders/:id" element={<OrderDetailsPage />} />
                <Route path="/refunds" element={<RefundsPage />} />
                <Route path="/refunds/:id" element={<RefundDetailsPage />} />
                <Route path="/services" element={<ServicesCatalogPage />} />
                <Route path="/services/:id" element={<ServiceDetailsPage />} />
                <Route path="/marketplace/profile" element={<MarketplaceProfilePage />} />
                <Route path="/marketplace/products" element={<MarketplaceProductsPage />} />
                <Route path="/marketplace/offers" element={<MarketplaceOffersPage />} />
                <Route path="/integrations" element={<IntegrationsPage />} />
                <Route path="/support/requests" element={<SupportRequestsPage />} />
                <Route path="/support/requests/:id" element={<SupportRequestDetailsPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/legal" element={<LegalPage />} />
              </Route>
            </Route>
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </LegalGateProvider>
      </PortalProvider>
    </AuthProvider>
  );
}
