import React, { useEffect, useState } from "react";
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

export const DashboardPage: React.FC = () => {
  const [operationsToday, setOperationsToday] = useState<number>(0);
  const [capturedYesterday, setCapturedYesterday] = useState<number>(0);
  const [billing, setBilling] = useState<BillingSummaryItem[]>([]);
  const [clearing, setClearing] = useState<ClearingBatch[]>([]);
  const [health, setHealth] = useState<ServiceHealth[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const today = new Date();
    const yesterday = new Date();
    yesterday.setDate(today.getDate() - 1);

    const load = async () => {
      try {
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

        setOperationsToday(opsToday.total ?? opsToday.items.length);
        const captured = billingData
          .filter((item) => item.date === getIsoDate(yesterday))
          .reduce((acc, item) => acc + item.total_captured_amount, 0);
        setCapturedYesterday(captured);
        setBilling(billingData);
        setClearing(clearingData);
        setHealth(healthData);
      } catch (err: any) {
        setError(err?.message ?? "Не удалось загрузить данные");
      }
    };

    void load();
  }, []);

  const pendingBilling = billing.filter((b) => b.status === "PENDING").length;
  const pendingClearing = clearing.filter((c) => c.status === "PENDING").length;
  const healthOk = health.every((h) => h.status === "ok");

  return (
    <div>
      <div className="page-header">
        <h1>Dashboard</h1>
        {error && <span style={{ color: "#dc2626" }}>{error}</span>}
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
