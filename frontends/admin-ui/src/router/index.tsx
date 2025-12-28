import React from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Loader } from "../components/Loader/Loader";
import { useAuth } from "../auth/AuthContext";

const Layout = React.lazy(() => import("../components/Layout/Layout"));
const DashboardPage = React.lazy(() => import("../pages/DashboardPage"));
const OperationsListPage = React.lazy(() => import("../pages/OperationsListPage"));
const OperationDetailsPage = React.lazy(() => import("../pages/OperationDetailsPage"));
const BillingSummaryPage = React.lazy(() => import("../pages/BillingSummaryPage"));
const ClearingBatchesPage = React.lazy(() => import("../pages/ClearingBatchesPage"));
const PayoutBatchesPage = React.lazy(() => import("../pages/PayoutBatchesPage"));
const BalancesPage = React.lazy(() => import("../pages/BalancesPage"));
const AccountDetailsPage = React.lazy(() => import("../pages/AccountDetailsPage"));
const IntegrationMonitoringPage = React.lazy(() => import("../pages/IntegrationMonitoringPage"));
const HealthPage = React.lazy(() => import("../pages/HealthPage"));
const LoginPage = React.lazy(() => import("../pages/LoginPage"));

export function AppRouter() {
  const { accessToken } = useAuth();

  return (
    <React.Suspense fallback={<Loader />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        {!accessToken ? (
          <Route path="*" element={<Navigate to="/login" replace />} />
        ) : (
          <Route element={<Layout />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/accounts" element={<BalancesPage />} />
            <Route path="/accounts/:accountId" element={<AccountDetailsPage />} />
            <Route path="/operations" element={<OperationsListPage />} />
            <Route path="/operations/:id" element={<OperationDetailsPage />} />
            <Route path="/integration" element={<IntegrationMonitoringPage />} />
            <Route path="/billing" element={<BillingSummaryPage />} />
            <Route path="/clearing" element={<ClearingBatchesPage />} />
            <Route path="/payouts" element={<PayoutBatchesPage />} />
            <Route path="/health" element={<HealthPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        )}
      </Routes>
    </React.Suspense>
  );
}
