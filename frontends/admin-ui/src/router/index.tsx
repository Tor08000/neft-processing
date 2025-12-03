import React from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Loader } from "../components/Loader/Loader";
import { useAuth } from "../auth/AuthContext";

const Layout = React.lazy(() => import("../components/Layout/Layout"));
const DashboardPage = React.lazy(() => import("../pages/DashboardPage"));
const OperationsListPage = React.lazy(() => import("../pages/OperationsListPage"));
const OperationDetailsPage = React.lazy(() => import("../pages/OperationDetailsPage"));
const BillingSummaryPage = React.lazy(() => import("../pages/BillingSummaryPage"));
const ClearingBatchesPage = React.lazy(() => import("../pages/ClearingBatchesPage"));
const HealthPage = React.lazy(() => import("../pages/HealthPage"));
const LoginPage = React.lazy(() => import("../pages/LoginPage"));

export function AppRouter() {
  const { token } = useAuth();

  return (
    <BrowserRouter>
      {!token ? (
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<LoginPage />} />
        </Routes>
      ) : (
        <React.Suspense fallback={<Loader />}>
          <Layout>
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/operations" element={<OperationsListPage />} />
              <Route path="/operations/:id" element={<OperationDetailsPage />} />
              <Route path="/billing" element={<BillingSummaryPage />} />
              <Route path="/clearing" element={<ClearingBatchesPage />} />
              <Route path="/health" element={<HealthPage />} />
              <Route path="/login" element={<LoginPage />} />
            </Routes>
          </Layout>
        </React.Suspense>
      )}
    </BrowserRouter>
  );
}
