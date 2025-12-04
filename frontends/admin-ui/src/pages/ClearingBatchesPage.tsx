import React, { Suspense, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchClearingBatches, fetchClearingBatchDetails, markBatchConfirmed, markBatchSent } from "../api/clearing";
import { StatusBadge } from "../components/StatusBadge/StatusBadge";
import { Table, type Column } from "../components/Table/Table";
import { formatAmount, formatDate } from "../utils/format";
import { ClearingBatch, ClearingBatchOperation } from "../types/clearing";
import { Loader } from "../components/Loader/Loader";

const DateRangeFilter = React.lazy(() =>
  import("../components/Filters/DateRangeFilter").then((mod) => ({ default: mod.DateRangeFilter })),
);
const SelectFilter = React.lazy(() =>
  import("../components/Filters/SelectFilter").then((mod) => ({ default: mod.SelectFilter })),
);

export const ClearingBatchesPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [batches, setBatches] = useState<ClearingBatch[]>([]);
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(null);
  const [dateRange, setDateRange] = useState<{ from?: string; to?: string }>({});
  const [status, setStatus] = useState<string>("");
  const [merchantId, setMerchantId] = useState<string>("");

  const filters = useMemo(
    () => ({
      date_from: dateRange.from,
      date_to: dateRange.to,
      status: status || undefined,
      merchant_id: merchantId || undefined,
    }),
    [dateRange.from, dateRange.to, merchantId, status],
  );

  const { data: batchesData = [], isFetching, isLoading, error, refetch } = useQuery({
    queryKey: ["clearing", filters],
    queryFn: () => fetchClearingBatches(filters),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
    placeholderData: (previousData) => previousData ?? [],
  });

  useEffect(() => {
    setBatches(batchesData);
    if (batchesData.length && !selectedBatchId) {
      setSelectedBatchId(batchesData[0].id);
    }
    if (batchesData.length && selectedBatchId && !batchesData.find((b) => b.id === selectedBatchId)) {
      setSelectedBatchId(batchesData[0].id);
    }
  }, [batchesData, selectedBatchId]);

  const {
    data: selectedBatchDetails,
    isFetching: isDetailsFetching,
  } = useQuery({
    queryKey: ["clearing", selectedBatchId, "details"],
    queryFn: () => fetchClearingBatchDetails(selectedBatchId!),
    enabled: Boolean(selectedBatchId),
    staleTime: 30_000,
  });

  const updateStatusMutation = useMutation({
    mutationFn: (action: "sent" | "confirmed") => {
      if (!selectedBatchId) return Promise.reject(new Error("No batch selected"));
      return action === "sent" ? markBatchSent(selectedBatchId) : markBatchConfirmed(selectedBatchId);
    },
    onSuccess: (updated) => {
      setBatches((prev) => prev.map((b) => (b.id === updated.id ? updated : b)));
      setSelectedBatchId(updated.id);
      queryClient.invalidateQueries({ queryKey: ["clearing", filters] });
    },
  });

  const updateStatus = (action: "sent" | "confirmed") => updateStatusMutation.mutate(action);

  const selectedBatch = useMemo(() => {
    const fromList = selectedBatchId ? batches.find((batch) => batch.id === selectedBatchId) : null;
    return selectedBatchDetails?.batch ?? fromList ?? null;
  }, [batches, selectedBatchDetails?.batch, selectedBatchId]);

  const operations = selectedBatchDetails?.operations ?? [];

  const batchColumns: Column<ClearingBatch>[] = [
    { key: "batch_date", title: "Batch Date", render: (row) => formatDate(row.batch_date) },
    { key: "merchant_id", title: "Merchant", render: (row) => row.merchant_id },
    { key: "currency", title: "Currency", render: (row) => row.currency },
    { key: "total_amount", title: "Total Amount", render: (row) => formatAmount(row.total_amount) },
    { key: "status", title: "Status", render: (row) => <StatusBadge status={row.status} /> },
  ];

  const batchOperationsColumns: Column<ClearingBatchOperation>[] = [
    { key: "id", title: "ID", render: (row) => row.id },
    { key: "operation", title: "Operation", render: (row) => row.operation_id },
    { key: "amount", title: "Amount", render: (row) => formatAmount(row.amount) },
  ];

  return (
    <div>
      <div className="page-header">
        <h1>Clearing</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => refetch()} disabled={isFetching}>
            Refresh
          </button>
          {(isLoading || isFetching || isDetailsFetching) && <Loader label="Синхронизация" />}
          {error && <span style={{ color: "#dc2626" }}>{error.message}</span>}
        </div>
      </div>

      <Suspense fallback={<Loader label="Загружаем фильтры" />}>
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
      </Suspense>

      <div className="card-grid" style={{ gridTemplateColumns: "2fr 1fr" }}>
        <div>
          <h2>Batches</h2>
          <Suspense fallback={<Loader label="Отрисовываем таблицу" />}>
            <Table columns={batchColumns} data={batches} onRowClick={(row) => setSelectedBatchId(row.id)} />
          </Suspense>
        </div>
        <div>
          <h2>Batch details</h2>
          {selectedBatch ? (
            <div className="card" style={{ marginBottom: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                <div>
                  <div style={{ fontWeight: 700 }}>{formatDate(selectedBatch.batch_date)}</div>
                  <div style={{ color: "#475569" }}>{selectedBatch.merchant_id}</div>
                </div>
                <StatusBadge status={selectedBatch.status} />
              </div>
              <p style={{ marginBottom: 4 }}>Currency: {selectedBatch.currency}</p>
              <p style={{ marginBottom: 4 }}>Total amount: {formatAmount(selectedBatch.total_amount)}</p>
              <p style={{ marginBottom: 12 }}>
                Operations: {selectedBatch.operations_count ?? operations.length}
              </p>
              <div className="actions">
                <button
                  onClick={() => updateStatus("sent")}
                  disabled={updateStatusMutation.isPending || selectedBatch.status !== "PENDING"}
                >
                  Mark sent
                </button>
                <button
                  onClick={() => updateStatus("confirmed")}
                  disabled={
                    updateStatusMutation.isPending ||
                    (selectedBatch.status !== "PENDING" && selectedBatch.status !== "SENT")
                  }
                >
                  Mark confirmed
                </button>
              </div>
            </div>
          ) : (
            <p>Select batch to view details</p>
          )}
          <h3>Operations</h3>
          <Suspense fallback={<Loader label="Загружаем операции батча" />}>
            <Table columns={batchOperationsColumns} data={operations} />
          </Suspense>
        </div>
      </div>
    </div>
  );
};

export default ClearingBatchesPage;
