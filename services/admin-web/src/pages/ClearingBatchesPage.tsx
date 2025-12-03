import React, { Suspense, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchClearingBatches,
  fetchClearingBatchOperations,
  markBatchConfirmed,
  markBatchSent,
} from "../api/clearing";
import { StatusBadge } from "../components/StatusBadge/StatusBadge";
import { formatAmount, formatDate } from "../utils/format";
import { ClearingBatch, ClearingBatchOperation } from "../types/clearing";
import { Loader } from "../components/Loader/Loader";

const Table = React.lazy(() => import("../components/Table/Table").then((mod) => ({ default: mod.Table })));
const DateRangeFilter = React.lazy(() =>
  import("../components/Filters/DateRangeFilter").then((mod) => ({ default: mod.DateRangeFilter })),
);
const SelectFilter = React.lazy(() =>
  import("../components/Filters/SelectFilter").then((mod) => ({ default: mod.SelectFilter })),
);

export const ClearingBatchesPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [batches, setBatches] = useState<ClearingBatch[]>([]);
  const [selectedBatch, setSelectedBatch] = useState<ClearingBatch | null>(null);
  const [operations, setOperations] = useState<ClearingBatchOperation[]>([]);
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

  const {
    data: batchesData = [],
    isFetching,
    isLoading,
    error,
    refetch,
  } = useQuery<ClearingBatch[], Error>({
    queryKey: ["clearing", filters],
    queryFn: () => fetchClearingBatches(filters),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
    keepPreviousData: true,
  });

  useEffect(() => {
    setBatches(batchesData);
    if (batchesData.length && !selectedBatch) {
      setSelectedBatch(batchesData[0]);
    }
  }, [batchesData, selectedBatch]);

  const { isFetching: isOperationsFetching } = useQuery<ClearingBatchOperation[], Error>({
    queryKey: ["clearing", selectedBatch?.id, "operations"],
    queryFn: async () => {
      const res = await fetchClearingBatchOperations(selectedBatch!.id);
      setOperations(res);
      return res;
    },
    enabled: Boolean(selectedBatch?.id),
    staleTime: 30_000,
  });

  const updateStatusMutation = useMutation({
    mutationFn: (action: "sent" | "confirmed") => {
      if (!selectedBatch) return Promise.reject(new Error("No batch selected"));
      return action === "sent" ? markBatchSent(selectedBatch.id) : markBatchConfirmed(selectedBatch.id);
    },
    onSuccess: (updated) => {
      setBatches((prev) => prev.map((b) => (b.id === updated.id ? updated : b)));
      setSelectedBatch(updated);
      queryClient.invalidateQueries({ queryKey: ["clearing", filters] });
    },
  });

  const updateStatus = (action: "sent" | "confirmed") => updateStatusMutation.mutate(action);

  return (
    <div>
      <div className="page-header">
        <h1>Clearing</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => refetch()} disabled={isFetching}>
            Refresh
          </button>
          {(isLoading || isFetching || isOperationsFetching) && <Loader label="Синхронизация" />}
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
          </Suspense>
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
          <Suspense fallback={<Loader label="Загружаем операции батча" />}>
            <Table<ClearingBatchOperation>
              columns={[
                { key: "id", title: "ID", render: (row) => row.id },
                { key: "operation", title: "Operation", render: (row) => row.operation_id },
                { key: "amount", title: "Amount", render: (row) => formatAmount(row.amount) },
              ]}
              data={operations}
            />
          </Suspense>
        </div>
      </div>
    </div>
  );
};
