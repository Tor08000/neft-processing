import React, { Suspense, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchBillingSummary, finalizeBillingSummary } from "../api/billing";
import { StatusBadge } from "../components/StatusBadge/StatusBadge";
import { Table, type Column } from "../components/Table/Table";
import { formatAmount, formatDate } from "../utils/format";
import { BillingSummaryItem } from "../types/billing";
import { Loader } from "../components/Loader/Loader";
const DateRangeFilter = React.lazy(() =>
  import("../components/Filters/DateRangeFilter").then((mod) => ({ default: mod.DateRangeFilter })),
);
const SelectFilter = React.lazy(() =>
  import("../components/Filters/SelectFilter").then((mod) => ({ default: mod.SelectFilter })),
);

export const BillingSummaryPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [dateRange, setDateRange] = useState<{ from: string; to: string }>(() => {
    const to = new Date();
    const from = new Date();
    from.setDate(to.getDate() - 7);
    return { from: from.toISOString().slice(0, 10), to: to.toISOString().slice(0, 10) };
  });
  const [status, setStatus] = useState<string>("");
  const [merchantId, setMerchantId] = useState<string>("");
  const filters = useMemo(
    () => ({
      date_from: dateRange.from,
      date_to: dateRange.to,
      merchant_id: merchantId || undefined,
      status: status || undefined,
    }),
    [dateRange.from, dateRange.to, merchantId, status],
  );

  const { data = [], isFetching, isLoading, error, refetch } = useQuery({
    queryKey: ["billing", filters],
    queryFn: () => fetchBillingSummary(filters),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
    placeholderData: (previousData) => previousData ?? [],
  });

  const finalizeMutation = useMutation({
    mutationFn: (id: string) => finalizeBillingSummary(id),
    onSuccess: (updated) => {
      queryClient.setQueryData<BillingSummaryItem[]>(["billing", filters], (previous) => {
        if (!previous) return previous;
        return previous.map((item) => (item.id === updated.id ? updated : item));
      });
    },
  });

  const handleFinalize = (id: string) => finalizeMutation.mutate(id);

  const columns: Column<BillingSummaryItem>[] = [
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
          <button onClick={() => handleFinalize(row.id)} disabled={finalizeMutation.isPending}>
            Finalize
          </button>
        ) : null,
    },
  ];

  return (
    <div>
      <div className="page-header">
        <h1>Billing summary</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => refetch()} disabled={isFetching}>
            Refresh
          </button>
          {(isLoading || isFetching) && <Loader label="Обновляем данные" />}
          {error && <span style={{ color: "#dc2626" }}>{error.message}</span>}
        </div>
      </div>

      <Suspense fallback={<Loader label="Инициализация фильтров" />}>
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
      </Suspense>

      <Suspense fallback={<Loader label="Загружаем таблицу" />}>
        <Table columns={columns} data={data} />
      </Suspense>
    </div>
  );
};

export default BillingSummaryPage;
