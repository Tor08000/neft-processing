import React, { useEffect, useState } from "react";
import { fetchBillingSummary, finalizeBillingSummary } from "../api/billing";
import { Table } from "../components/Table/Table";
import { StatusBadge } from "../components/StatusBadge/StatusBadge";
import { DateRangeFilter } from "../components/Filters/DateRangeFilter";
import { SelectFilter } from "../components/Filters/SelectFilter";
import { formatAmount, formatDate } from "../utils/format";
import { BillingSummaryItem } from "../types/billing";

export const BillingSummaryPage: React.FC = () => {
  const [data, setData] = useState<BillingSummaryItem[]>([]);
  const [dateRange, setDateRange] = useState<{ from: string; to: string }>(() => {
    const to = new Date();
    const from = new Date();
    from.setDate(to.getDate() - 7);
    return { from: from.toISOString().slice(0, 10), to: to.toISOString().slice(0, 10) };
  });
  const [status, setStatus] = useState<string>("");
  const [merchantId, setMerchantId] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchBillingSummary({
        date_from: dateRange.from,
        date_to: dateRange.to,
        merchant_id: merchantId || undefined,
        status: status || undefined,
      });
      setData(res);
    } catch (err: any) {
      setError(err?.message ?? "Не удалось загрузить billing summary");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const handleFinalize = async (id: string) => {
    try {
      const updated = await finalizeBillingSummary(id);
      setData((prev) => prev.map((item) => (item.id === id ? updated : item)));
    } catch (err: any) {
      setError(err?.message ?? "Не удалось финализировать");
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1>Billing summary</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => load()} disabled={loading}>
            Refresh
          </button>
          {loading && <span>Loading...</span>}
          {error && <span style={{ color: "#dc2626" }}>{error}</span>}
        </div>
      </div>

      <div className="filters">
        <DateRangeFilter
          label="Dates"
          from={dateRange.from}
          to={dateRange.to}
          onChange={(range) => setDateRange({ from: range.from || "", to: range.to || "" })}
        />
        <SelectFilter
          label="Status"
          value={status}
          onChange={setStatus}
          options={[
            { value: "PENDING", label: "PENDING" },
            { value: "FINALIZED", label: "FINALIZED" },
          ]}
        />
        <div className="filter">
          <span className="label">Merchant</span>
          <input value={merchantId} onChange={(e) => setMerchantId(e.target.value)} placeholder="merchant id" />
        </div>
      </div>

      <Table<BillingSummaryItem>
        columns={[
          { key: "date", title: "Date", render: (row) => formatDate(row.date) },
          { key: "merchant", title: "Merchant", render: (row) => row.merchant_id },
          {
            key: "amount",
            title: "Captured",
            render: (row) => formatAmount(row.total_captured_amount),
          },
          { key: "count", title: "Ops", render: (row) => row.operations_count },
          { key: "hash", title: "Hash", render: (row) => row.hash || "-" },
          { key: "status", title: "Status", render: (row) => <StatusBadge status={row.status} /> },
          {
            key: "actions",
            title: "Actions",
            render: (row) =>
              row.status === "PENDING" ? (
                <button onClick={() => handleFinalize(row.id)} disabled={loading}>
                  Finalize
                </button>
              ) : null,
          },
        ]}
        data={data}
      />
    </div>
  );
};
