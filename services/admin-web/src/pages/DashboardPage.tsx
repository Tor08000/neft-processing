import React from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchOperations } from "../api/operations";
import { fetchBillingSummary } from "../api/billing";
import { fetchClearingBatches } from "../api/clearing";
import { fetchHealth } from "../api/health";
import { SummaryCard } from "../components/SummaryCard/SummaryCard";
import { StatusBadge } from "../components/StatusBadge/StatusBadge";
import { formatAmount, getIsoDate } from "../utils/format";
import { BillingSummaryItem } from "../types/billing";
import { ClearingBatch } from "../types/clearing";
import { ServiceHealth } from "../types/health";
import { Loader } from "../components/Loader/Loader";

interface DashboardData {
  operationsToday: number;
  capturedYesterday: number;
  billing: BillingSummaryItem[];
  clearing: ClearingBatch[];
  health: ServiceHealth[];
}

export const DashboardPage: React.FC = () => {
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);

  const { data, error, isLoading, isFetching } = useQuery<DashboardData, Error>({
    queryKey: ["dashboard"],
    queryFn: async () => {
      const [opsToday, billingData, clearingData, healthData] = await Promise.all([
        fetchOperations({
          date_from: getIsoDate(today),
          date_to: getIsoDate(today),
          limit: 1,
          offset: 0,
        }),
        fetchBillingSummary({ date_from: getIsoDate(yesterday), date_to: getIsoDate(today) }),
        fetchClearingBatches({ status: "PENDING" }),
        fetchHealth(),
      ]);

      const operationsToday = opsToday.total ?? opsToday.items.length;
      const capturedYesterday = billingData
        .filter((item) => item.date === getIsoDate(yesterday))
        .reduce((acc, item) => acc + item.total_captured_amount, 0);

      return {
        operationsToday,
        capturedYesterday,
        billing: billingData,
        clearing: clearingData,
        health: healthData,
      };
    },
    staleTime: 5_000,
    refetchOnWindowFocus: false,
  });

  const billing = data?.billing ?? [];
  const clearing = data?.clearing ?? [];
  const health = data?.health ?? [];
  const operationsToday = data?.operationsToday ?? 0;
  const capturedYesterday = data?.capturedYesterday ?? 0;

  const pendingBilling = billing.filter((b) => b.status === "PENDING").length;
  const pendingClearing = clearing.filter((c) => c.status === "PENDING").length;
  const healthOk = health.every((h) => h.status === "ok");

  return (
    <div>
      <div className="page-header">
        <h1>Dashboard</h1>
        {(isLoading || isFetching) && <Loader label="Обновляем метрики" />}
        {error && <span style={{ color: "#dc2626" }}>{error.message}</span>}
      </div>
      <div className="card-grid">
        <SummaryCard title="Operations today" value={operationsToday} />
        <SummaryCard title="Captured yesterday" value={formatAmount(capturedYesterday)} />
        <SummaryCard title="Billing (pending)" value={pendingBilling} />
        <SummaryCard title="Clearing (pending)" value={pendingClearing} />
        <SummaryCard
          title="Backend health"
          value={
            <StatusBadge status={healthOk ? "OK" : health.length ? "DEGRADED" : "UNKNOWN"} />
          }
        />
      </div>
    </div>
  );
};
