import React, { useEffect, useMemo, useState } from "react";
import { fetchInvoices } from "../api/billing";
import { Table, type Column } from "../components/Table/Table";
import type { Invoice } from "../types/billing";
import { formatAmount } from "../utils/format";

interface InvoiceKpi {
  label: string;
  value: number;
}

export const BillingDashboardPage: React.FC = () => {
  const today = new Date();
  const defaultFrom = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().slice(0, 10);
  const defaultTo = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().slice(0, 10);

  const [periodFrom, setPeriodFrom] = useState(defaultFrom);
  const [periodTo, setPeriodTo] = useState(defaultTo);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    fetchInvoices({ period_from: periodFrom, period_to: periodTo })
      .then((res) => setInvoices(res.items))
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [periodFrom, periodTo]);

  const kpis: InvoiceKpi[] = useMemo(() => {
    const total = invoices.reduce((acc, inv) => acc + (inv.total_with_tax ?? inv.total_amount ?? 0), 0);
    const byStatus: Record<string, number> = {};
    invoices.forEach((inv) => {
      byStatus[inv.status] = (byStatus[inv.status] ?? 0) + 1;
    });
    return [
      { label: "Billed total", value: total },
      { label: "Draft", value: byStatus.DRAFT ?? 0 },
      { label: "Issued", value: byStatus.ISSUED ?? 0 },
      { label: "Paid", value: byStatus.PAID ?? 0 },
    ];
  }, [invoices]);

  const topClients = useMemo(() => {
    const aggregated: Record<string, number> = {};
    invoices.forEach((inv) => {
      aggregated[inv.client_id] = (aggregated[inv.client_id] ?? 0) + inv.total_with_tax;
    });
    return Object.entries(aggregated)
      .map(([client, amount]) => ({ client, amount }))
      .sort((a, b) => b.amount - a.amount)
      .slice(0, 5);
  }, [invoices]);

  const columns: Column<Invoice>[] = [
    { key: "client", title: "Client", render: (row) => row.client_id },
    { key: "period", title: "Period", render: (row) => `${row.period_from} — ${row.period_to}` },
    { key: "amount", title: "Amount", render: (row) => formatAmount(row.total_with_tax ?? row.total_amount) },
    { key: "status", title: "Status", render: (row) => row.status },
  ];

  return (
    <div>
      <h1>Billing dashboard</h1>
      <div className="filters">
        <label className="filter">
          <span className="label">From</span>
          <input type="date" value={periodFrom} onChange={(e) => setPeriodFrom(e.target.value)} />
        </label>
        <label className="filter">
          <span className="label">To</span>
          <input type="date" value={periodTo} onChange={(e) => setPeriodTo(e.target.value)} />
        </label>
        {loading && <span>Loading…</span>}
        {error && <span style={{ color: "#dc2626" }}>{error}</span>}
      </div>

      <div style={{ display: "flex", gap: 16, margin: "16px 0" }}>
        {kpis.map((item) => (
          <div key={item.label} style={{ padding: 12, background: "#fff", borderRadius: 10, minWidth: 140 }}>
            <div style={{ color: "#475569" }}>{item.label}</div>
            <div style={{ fontWeight: 700 }}>{item.label === "Billed total" ? formatAmount(item.value) : item.value}</div>
          </div>
        ))}
      </div>

      <div style={{ marginBottom: 12 }}>
        <h2>Top clients</h2>
        <ul>
          {topClients.map((row) => (
            <li key={row.client}>{`${row.client}: ${formatAmount(row.amount)}`}</li>
          ))}
          {topClients.length === 0 && <li>No data</li>}
        </ul>
      </div>

      <Table columns={columns} data={invoices} />
    </div>
  );
};

export default BillingDashboardPage;
