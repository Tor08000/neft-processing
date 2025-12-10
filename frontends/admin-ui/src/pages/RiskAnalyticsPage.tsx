import React, { Suspense, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchOperations } from "../api/operations";
import { Table, type Column } from "../components/Table/Table";
import { Loader } from "../components/Loader/Loader";
import { RiskBadge } from "../components/RiskBadge/RiskBadge";
import { formatAmount, formatDateTime } from "../utils/format";
import { Operation } from "../types/operations";

const DateRangeFilter = React.lazy(() =>
  import("../components/Filters/DateRangeFilter").then((mod) => ({ default: mod.DateRangeFilter })),
);

const RISK_LEVELS = ["LOW", "MEDIUM", "HIGH", "BLOCK"] as const;

export const RiskAnalyticsPage: React.FC = () => {
  const navigate = useNavigate();
  const [dateRange, setDateRange] = useState<{ from: string; to: string }>(() => {
    const to = new Date();
    const from = new Date();
    from.setDate(to.getDate() - 7);
    return { from: from.toISOString().slice(0, 10), to: to.toISOString().slice(0, 10) };
  });
  const [riskLevel, setRiskLevel] = useState<string>("ANY");
  const [clientId, setClientId] = useState<string>("");
  const [merchantId, setMerchantId] = useState<string>("");

  const filters = useMemo(
    () => ({
      limit: 200,
      offset: 0,
      order_by: "risk_score_desc" as const,
      from_created_at: dateRange.from ? `${dateRange.from}T00:00:00Z` : undefined,
      to_created_at: dateRange.to ? `${dateRange.to}T23:59:59Z` : undefined,
      risk_result: riskLevel !== "ANY" ? riskLevel : undefined,
      client_id: clientId || undefined,
      merchant_id: merchantId || undefined,
    }),
    [clientId, dateRange.from, dateRange.to, merchantId, riskLevel],
  );

  const { data, isFetching, isLoading, error, refetch } = useQuery({
    queryKey: ["risk-analytics", filters],
    queryFn: () => fetchOperations(filters),
    staleTime: 30_000,
    refetchOnWindowFocus: false,
    placeholderData: (previous) => previous,
  });

  const operations = data?.items ?? [];

  const totals = useMemo(() => {
    const counts: Record<string, number> = {};
    operations.forEach((op) => {
      const level = (op.risk_result || "UNKNOWN").toUpperCase();
      counts[level] = (counts[level] || 0) + 1;
    });
    const total = operations.length;
    return { counts, total };
  }, [operations]);

  const columns: Column<Operation>[] = [
    { key: "created_at", title: "Дата", render: (row) => formatDateTime(row.created_at) },
    { key: "client_id", title: "Клиент", render: (row) => row.client_id },
    { key: "merchant_id", title: "Мерчант", render: (row) => row.merchant_id },
    { key: "amount", title: "Сумма", render: (row) => `${formatAmount(row.amount)} ${row.currency}` },
    {
      key: "risk_result",
      title: "Риск",
      render: (row) => <RiskBadge level={row.risk_result} score={row.risk_score ?? undefined} />,
    },
    {
      key: "risk_reasons",
      title: "Причины",
      render: (row) => row.risk_reasons?.join(", ") || "—",
    },
  ];

  return (
    <div>
      <div className="page-header">
        <h1>Risk analytics</h1>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button onClick={() => refetch()} disabled={isFetching}>
            Refresh
          </button>
          {(isLoading || isFetching) && <Loader label="Обновляем данные" />}
          {error && <span style={{ color: "#dc2626" }}>{(error as Error).message}</span>}
        </div>
      </div>

      <Suspense fallback={<Loader label="Инициализация фильтров" />}>
        <div className="filters">
          <DateRangeFilter
            label="Даты"
            from={dateRange.from}
            to={dateRange.to}
            onChange={(range) => setDateRange({ from: range.from || "", to: range.to || "" })}
          />
          <div className="filter">
            <span className="label">Risk</span>
            <select value={riskLevel} onChange={(e) => setRiskLevel(e.target.value)}>
              <option value="ANY">Любой</option>
              {RISK_LEVELS.map((level) => (
                <option key={level} value={level}>
                  {level}
                </option>
              ))}
            </select>
          </div>
          <div className="filter">
            <span className="label">Client</span>
            <input value={clientId} onChange={(e) => setClientId(e.target.value)} placeholder="client id" />
          </div>
          <div className="filter">
            <span className="label">Merchant</span>
            <input value={merchantId} onChange={(e) => setMerchantId(e.target.value)} placeholder="merchant id" />
          </div>
        </div>
      </Suspense>

      <div className="card-grid" style={{ marginBottom: 16 }}>
        <div className="card">
          <h3>Всего операций</h3>
          <p style={{ fontSize: 24, fontWeight: 700 }}>{totals.total}</p>
        </div>
        {RISK_LEVELS.map((level) => {
          const count = totals.counts[level] || 0;
          const percent = totals.total ? Math.round((count / totals.total) * 100) : 0;
          return (
            <div key={level} className="card">
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <RiskBadge level={level} />
                <div style={{ fontSize: 18, fontWeight: 700 }}>{count}</div>
              </div>
              <p style={{ marginTop: 8, color: "#475569" }}>{percent}% от выборки</p>
            </div>
          );
        })}
      </div>

      <h2>Топ рискованных операций</h2>
      <Suspense fallback={<Loader label="Загружаем операции" />}>
        <Table columns={columns} data={operations.slice(0, 50)} onRowClick={(row) => navigate(`/operations/${row.operation_id}`)} />
      </Suspense>
    </div>
  );
};

export default RiskAnalyticsPage;
