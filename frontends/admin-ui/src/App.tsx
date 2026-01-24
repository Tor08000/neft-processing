import { Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { LegalGateProvider } from "./auth/LegalGateContext";
import { LoginPage } from "./pages/LoginPage";
import { AdminProvider } from "./admin/AdminContext";
import { AdminAuthGuard } from "./admin/AdminAuthGuard";
import { AdminErrorBoundary } from "./admin/AdminErrorBoundary";
import { AdminShell } from "./admin/AdminShell";
import { AdminRBACGate } from "./admin/AdminRBACGate";
import AdminDashboardPage from "./pages/admin/AdminDashboardPage";
import ComingSoonPage from "./pages/admin/ComingSoonPage";
import { AdminNotFoundPage } from "./pages/admin/AdminStatusPages";
import OpsOverviewPage from "./pages/ops/OpsOverviewPage";
import OpsBlockedPayoutsPage from "./pages/ops/OpsBlockedPayoutsPage";
import OpsFailedExportsPage from "./pages/ops/OpsFailedExportsPage";
import OpsFailedImportsPage from "./pages/ops/OpsFailedImportsPage";
import OpsSupportBreachesPage from "./pages/ops/OpsSupportBreachesPage";
import OpsDrilldownPlaceholderPage from "./pages/ops/OpsDrilldownPlaceholderPage";
import RuntimeCenterPage from "./pages/admin/RuntimeCenterPage";
import FinanceOverviewPage from "./pages/finance/FinanceOverviewPage";
import InvoicesPage from "./pages/finance/InvoicesPage";
import InvoiceDetailsPage from "./pages/finance/InvoiceDetailsPage";
import PaymentIntakesPage from "./pages/finance/PaymentIntakesPage";
import ReconciliationImportsPage from "./pages/finance/ReconciliationImportsPage";
import ReconciliationImportDetailsPage from "./pages/finance/ReconciliationImportDetailsPage";
import PayoutQueuePage from "./pages/finance/PayoutQueuePage";
import PayoutDetailsPage from "./pages/finance/PayoutDetailsPage";

export function App() {
  return (
    <AuthProvider>
      <LegalGateProvider>
        <AdminProvider>
          <AdminErrorBoundary>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route element={<AdminAuthGuard />}>
                <Route element={<AdminShell />}>
                  <Route path="/" element={<AdminDashboardPage />} />
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
                      <AdminRBACGate permission="ops">
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
                    path="/ops/drilldown"
                    element={
                      <AdminRBACGate permission="ops">
                        <OpsDrilldownPlaceholderPage />
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
                    path="/sales"
                    element={
                      <AdminRBACGate permission="sales">
                        <ComingSoonPage title="Sales" />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/legal"
                    element={
                      <AdminRBACGate permission="legal">
                        <ComingSoonPage title="Legal" />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/audit"
                    element={
                      <AdminRBACGate permission="superadmin">
                        <ComingSoonPage title="Audit" />
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
