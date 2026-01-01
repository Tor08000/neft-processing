import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { fetchInvoice, updateInvoiceStatus } from "../api/billing";
import { Table, type Column } from "../components/Table/Table";
import type { Invoice, InvoiceLine, InvoiceStatus } from "../types/billing";
import { formatAmount } from "../utils/format";

export const InvoiceDetailsPage: React.FC = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    fetchInvoice(id)
      .then((res) => setInvoice(res))
      .catch((err: Error) => setError(err.message));
  }, [id]);

  const handleStatusChange = async (next: InvoiceStatus) => {
    if (!id) return;
    const updated = await updateInvoiceStatus(id, next);
    setInvoice(updated);
  };

  const columns: Column<InvoiceLine>[] = [
    { key: "product", title: "Product", render: (row) => row.product_id },
    { key: "liters", title: "Liters", render: (row) => row.liters ?? "" },
    { key: "unit", title: "Unit price", render: (row) => row.unit_price ?? "" },
    { key: "amount", title: "Amount", render: (row) => formatAmount(row.line_amount) },
    { key: "tax", title: "Tax", render: (row) => formatAmount(row.tax_amount) },
    { key: "card", title: "Card", render: (row) => row.card_id ?? "" },
  ];

  if (!invoice) {
    return <div>{error ? error : "Loading invoice..."}</div>;
  }

  return (
    <div>
      <h1>Invoice {invoice.id}</h1>
      <p>
        Client {invoice.client_id} • Period {invoice.period_from} — {invoice.period_to}
      </p>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <button type="button" onClick={() => navigate(`/money/invoices/${invoice.id}/cfo-explain`)}>
          CFO explain
        </button>
        <button type="button" onClick={() => navigate(`/money/invoices/${invoice.id}/cfo-explain?view=money`)}>
          Money explain
        </button>
        <button type="button" onClick={() => navigate(`/explain?kind=invoice&id=${encodeURIComponent(invoice.id)}`)}>
          Explain
        </button>
        <button
          type="button"
          onClick={() => navigate(`/explain?kind=invoice&id=${encodeURIComponent(invoice.id)}&diff=1`)}
        >
          Сравнить
        </button>
      </div>
      <p>
        Amount: {formatAmount(invoice.total_with_tax ?? invoice.total_amount)} • Status: {invoice.status}
      </p>
      <select value={invoice.status} onChange={(e) => handleStatusChange(e.target.value as InvoiceStatus)}>
        <option value="DRAFT">Draft</option>
        <option value="ISSUED">Issued</option>
        <option value="SENT">Sent</option>
        <option value="PAID">Paid</option>
      </select>

      <Table columns={columns} data={invoice.lines ?? []} />
    </div>
  );
};

export default InvoiceDetailsPage;
