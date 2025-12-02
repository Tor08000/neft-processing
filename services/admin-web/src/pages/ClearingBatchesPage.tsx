import React, { useEffect, useState } from "react";
import {
  fetchClearingBatches,
  fetchClearingBatchOperations,
  markBatchConfirmed,
  markBatchSent,
} from "../api/clearing";
import { Table } from "../components/Table/Table";
import { StatusBadge } from "../components/StatusBadge/StatusBadge";
import { DateRangeFilter } from "../components/Filters/DateRangeFilter";
import { SelectFilter } from "../components/Filters/SelectFilter";
import { formatAmount, formatDate } from "../utils/format";
import { ClearingBatch, ClearingBatchOperation } from "../types/clearing";

export const ClearingBatchesPage: React.FC = () => {
  const [batches, setBatches] = useState<ClearingBatch[]>([]);
  const [selectedBatch, setSelectedBatch] = useState<ClearingBatch | null>(null);
  const [operations, setOperations] = useState<ClearingBatchOperation[]>([]);
  const [dateRange, setDateRange] = useState<{ from?: string; to?: string }>({});
  const [status, setStatus] = useState<string>("");
  const [merchantId, setMerchantId] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadBatches = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchClearingBatches({
        date_from: dateRange.from,
        date_to: dateRange.to,
        status: status || undefined,
        merchant_id: merchantId || undefined,
      });
      setBatches(res);
      if (res.length > 0) {
        setSelectedBatch(res[0]);
      }
    } catch (err: any) {
      setError(err?.message ?? "Не удалось загрузить clearing batches");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadBatches();
  }, []);

  useEffect(() => {
    if (!selectedBatch) return;
    const loadOperations = async () => {
      try {
        const res = await fetchClearingBatchOperations(selectedBatch.id);
        setOperations(res);
      } catch (err: any) {
        setError(err?.message ?? "Не удалось загрузить операции батча");
      }
    };

    void loadOperations();
  }, [selectedBatch]);

  const updateStatus = async (action: "sent" | "confirmed") => {
    if (!selectedBatch) return;
    try {
      const updated =
        action === "sent"
          ? await markBatchSent(selectedBatch.id)
          : await markBatchConfirmed(selectedBatch.id);
      setBatches((prev) => prev.map((b) => (b.id === updated.id ? updated : b)));
      setSelectedBatch(updated);
    } catch (err: any) {
      setError(err?.message ?? "Не удалось обновить статус");
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1>Clearing</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => loadBatches()} disabled={loading}>
            Refresh
          </button>
          {loading && <span>Loading...</span>}
          {error && <span style={{ color: "#dc2626" }}>{error}</span>}
        </div>
      </div>

      <div className="filters">
        <SelectFilter
          label="Status"
          value={status}
          onChange={setStatus}
          options={[
            { value: "PENDING", label: "PENDING" },
            { value: "SENT", label: "SENT" },
            { value: "CONFIRMED", label: "CONFIRMED" },
            { value: "FAILED", label: "FAILED" },
          ]}
        />
        <DateRangeFilter label="Dates" from={dateRange.from} to={dateRange.to} onChange={setDateRange} />
        <div className="filter">
          <span className="label">Merchant</span>
          <input value={merchantId} onChange={(e) => setMerchantId(e.target.value)} placeholder="merchant id" />
        </div>
      </div>

      <div className="card-grid" style={{ gridTemplateColumns: "2fr 1fr" }}>
        <div>
          <h2>Batches</h2>
          <Table<ClearingBatch>
            columns={[
              { key: "id", title: "ID", render: (row) => row.id },
              { key: "merchant", title: "Merchant", render: (row) => row.merchant_id },
              { key: "range", title: "Range", render: (row) => `${formatDate(row.date_from)} → ${formatDate(row.date_to)}` },
              { key: "amount", title: "Amount", render: (row) => formatAmount(row.total_amount) },
              { key: "ops", title: "Ops", render: (row) => row.operations_count },
              { key: "status", title: "Status", render: (row) => <StatusBadge status={row.status} /> },
            ]}
            data={batches}
            onRowClick={(row) => setSelectedBatch(row)}
          />
        </div>
        <div>
          <h2>Operations in batch</h2>
          {selectedBatch ? (
            <div className="card">
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                <div>
                  <div style={{ fontWeight: 700 }}>{selectedBatch.id}</div>
                  <div style={{ color: "#475569" }}>{selectedBatch.merchant_id}</div>
                </div>
                <StatusBadge status={selectedBatch.status} />
              </div>
              <p style={{ marginBottom: 8 }}>
                {formatDate(selectedBatch.date_from)} → {formatDate(selectedBatch.date_to)}
              </p>
              <p style={{ marginBottom: 8 }}>Amount: {formatAmount(selectedBatch.total_amount)}</p>
              <div className="actions">
                <button onClick={() => updateStatus("sent")} disabled={loading || selectedBatch.status !== "PENDING"}>
                  Mark sent
                </button>
                <button
                  onClick={() => updateStatus("confirmed")}
                  disabled={loading || (selectedBatch.status !== "PENDING" && selectedBatch.status !== "SENT")}
                >
                  Mark confirmed
                </button>
              </div>
            </div>
          ) : (
            <p>Select batch to view details</p>
          )}
          <Table<ClearingBatchOperation>
            columns={[
              { key: "id", title: "ID", render: (row) => row.id },
              { key: "operation", title: "Operation", render: (row) => row.operation_id },
              { key: "amount", title: "Amount", render: (row) => formatAmount(row.amount) },
            ]}
            data={operations}
          />
        </div>
      </div>
    </div>
  );
};
