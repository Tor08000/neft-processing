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

export const BillingSummaryPage: React.FC = () => {
  const queryClient = useQueryClient();
  const [dateRange, setDateRange] = useState<{ from: string; to: string }>(() => {
    const to = new Date();
    const from = new Date();
    from.setDate(to.getDate() - 7);
    return { from: from.toISOString().slice(0, 10), to: to.toISOString().slice(0, 10) };
  });
  const [merchantId, setMerchantId] = useState<string>("");
  const [clientId, setClientId] = useState<string>("");
  const [productType, setProductType] = useState<string>("");
  const filters = useMemo(
    () => ({
      date_from: dateRange.from,
      date_to: dateRange.to,
      client_id: clientId || undefined,
      merchant_id: merchantId || undefined,
      product_type: productType || undefined,
    }),
    [clientId, dateRange.from, dateRange.to, merchantId, productType],
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
    { key: "billing_date", title: "Billing Date", render: (row) => formatDate(row.billing_date) },
    { key: "client_id", title: "Client", render: (row) => row.client_id },
    { key: "merchant_id", title: "Merchant", render: (row) => row.merchant_id },
    { key: "product_type", title: "Product", render: (row) => row.product_type },
    { key: "currency", title: "Currency", render: (row) => row.currency },
    { key: "total_amount", title: "Total Amount", render: (row) => formatAmount(row.total_amount) },
    { key: "total_quantity", title: "Quantity", render: (row) => row.total_quantity },
    { key: "operations_count", title: "Operations", render: (row) => row.operations_count },
    { key: "commission_amount", title: "Commission", render: (row) => formatAmount(row.commission_amount) },
    { key: "status", title: "Status", render: (row) => <StatusBadge status={row.status ?? ""} /> },
    {
      key: "actions",
      title: "Actions",
      render: (row) => {
        const summaryId = row.id;
        if (!summaryId || row.status !== "PENDING") return null;

        return (
          <button onClick={() => handleFinalize(summaryId)} disabled={finalizeMutation.isPending}>
            Finalize
          </button>
        );
      },
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
          <div className="filter">
            <span className="label">Client</span>
            <input value={clientId} onChange={(e) => setClientId(e.target.value)} placeholder="client id" />
          </div>
          <div className="filter">
            <span className="label">Merchant</span>
            <input value={merchantId} onChange={(e) => setMerchantId(e.target.value)} placeholder="merchant id" />
          </div>
          <div className="filter">
            <span className="label">Product type</span>
            <input
              value={productType}
              onChange={(e) => setProductType(e.target.value)}
              placeholder="product type"
            />
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
