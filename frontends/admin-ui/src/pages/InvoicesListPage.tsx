import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchInvoices, generateInvoices } from "../api/billing";
import { Table, type Column } from "../components/Table/Table";
import type { Invoice, InvoiceStatus } from "../types/billing";
import { formatAmount } from "../utils/format";

export const InvoicesListPage: React.FC = () => {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<{ client_id?: string; status?: InvoiceStatus }>({});
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [periodFrom, setPeriodFrom] = useState("");
  const [periodTo, setPeriodTo] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    fetchInvoices({ ...filters, period_from: periodFrom || undefined, period_to: periodTo || undefined })
      .then((res) => setInvoices(res.items))
      .catch((err: Error) => setMessage(err.message));
  }, [filters, periodFrom, periodTo]);

  const handleGenerate = async () => {
    const from = periodFrom || new Date().toISOString().slice(0, 10);
    const to = periodTo || from;
    const result = await generateInvoices({ period_from: from, period_to: to });
    setMessage(`Created ${result.created_ids.length} invoices`);
  };

  const columns: Column<Invoice>[] = [
    { key: "client", title: "Client", render: (row) => row.client_id },
    { key: "period", title: "Period", render: (row) => `${row.period_from} - ${row.period_to}` },
    { key: "amount", title: "Amount", render: (row) => formatAmount(row.total_with_tax ?? row.total_amount) },
    { key: "status", title: "Status", render: (row) => row.status },
    { key: "created", title: "Created", render: (row) => row.created_at ?? "" },
  ];

  return (
    <div>
      <h1>Invoices</h1>
      <div className="filters" style={{ display: "flex", gap: 8 }}>
        <input placeholder="Client" value={filters.client_id ?? ""} onChange={(e) => setFilters({ ...filters, client_id: e.target.value || undefined })} />
        <select
          value={filters.status ?? ""}
          onChange={(e) => setFilters({ ...filters, status: (e.target.value || undefined) as InvoiceStatus | undefined })}
        >
          <option value="">Any status</option>
          <option value="DRAFT">Draft</option>
          <option value="ISSUED">Issued</option>
          <option value="PAID">Paid</option>
        </select>
        <input type="date" value={periodFrom} onChange={(e) => setPeriodFrom(e.target.value)} />
        <input type="date" value={periodTo} onChange={(e) => setPeriodTo(e.target.value)} />
        <button onClick={handleGenerate}>Generate invoices</button>
        {message && <span>{message}</span>}
      </div>

      <Table columns={columns} data={invoices} onRowClick={(row) => navigate(`/billing/invoices/${row.id}`)} />
    </div>
  );
};

export default InvoicesListPage;
