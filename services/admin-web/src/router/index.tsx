import React from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "../components/Layout/Layout";
import { DashboardPage } from "../pages/DashboardPage";
import { OperationsListPage } from "../pages/OperationsListPage";
import { OperationDetailsPage } from "../pages/OperationDetailsPage";
import { BillingSummaryPage } from "../pages/BillingSummaryPage";
import { ClearingBatchesPage } from "../pages/ClearingBatchesPage";
import { HealthPage } from "../pages/HealthPage";

export function AppRouter() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/operations" element={<OperationsListPage />} />
          <Route path="/operations/:id" element={<OperationDetailsPage />} />
          <Route path="/billing" element={<BillingSummaryPage />} />
          <Route path="/clearing" element={<ClearingBatchesPage />} />
          <Route path="/health" element={<HealthPage />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
