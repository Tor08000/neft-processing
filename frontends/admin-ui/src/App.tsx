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
                        <ComingSoonPage title="Ops" />
                      </AdminRBACGate>
                    }
                  />
                  <Route
                    path="/finance"
                    element={
                      <AdminRBACGate permission="finance">
                        <ComingSoonPage title="Finance" />
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
