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
  const [reasonFilter, setReasonFilter] = useState<string>("");

  const filters = useMemo(
    () => ({
      limit: 200,
      offset: 0,
      order_by: "risk_score_desc" as const,
      from_created_at: dateRange.from ? `${dateRange.from}T00:00:00Z` : undefined,
      to_created_at: dateRange.to ? `${dateRange.to}T23:59:59Z` : undefined,
      risk_result: riskLevel !== "ANY" ? [riskLevel] : undefined,
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

  const filteredOperations = useMemo(() => {
    const reasonSearch = reasonFilter.trim().toLowerCase();
    if (!reasonSearch) return operations;
    return operations.filter((op) =>
      (op.risk_reasons || []).some((reason) => reason.toLowerCase().includes(reasonSearch)),
    );
  }, [operations, reasonFilter]);

  const totals = useMemo(() => {
    const counts: Record<string, number> = {};
    filteredOperations.forEach((op) => {
      const level = (op.risk_result || "UNKNOWN").toUpperCase();
      counts[level] = (counts[level] || 0) + 1;
    });
    const total = filteredOperations.length;
    return { counts, total };
  }, [filteredOperations]);

  const highRiskOperations = useMemo(() => {
    const result = filteredOperations.filter((op) => {
      const severity = (op.risk_result || "").toUpperCase();
      const decision = (op.risk_level || "").toUpperCase();
      return ["HIGH", "BLOCK"].includes(severity) || decision === "HARD_DECLINE";
    });
    return result.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  }, [filteredOperations]);

  const topByRiskScore = useMemo(() => {
    return [...filteredOperations].sort((a, b) => (b.risk_score ?? 0) - (a.risk_score ?? 0));
  }, [filteredOperations]);

  const columns: Column<Operation>[] = [
    { key: "created_at", title: "Дата", render: (row) => formatDateTime(row.created_at) },
    { key: "client_id", title: "Клиент", render: (row) => row.client_id },
    { key: "merchant_id", title: "Мерчант", render: (row) => row.merchant_id },
    { key: "amount", title: "Сумма", render: (row) => `${formatAmount(row.amount)} ${row.currency}` },
    {
      key: "risk_result",
      title: "Риск",
      render: (row) => (
        <RiskBadge
          level={row.risk_result}
          decision={row.risk_level}
          score={row.risk_score ?? undefined}
          reasons={row.risk_reasons ?? undefined}
          source={row.risk_source ?? undefined}
        />
      ),
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
          <div className="filter">
            <span className="label">Reason code</span>
            <input
              value={reasonFilter}
              onChange={(e) => setReasonFilter(e.target.value)}
              placeholder="velocity / blacklist ..."
            />
            <button
              style={{ marginTop: 6 }}
              onClick={() => reasonFilter && navigate(`/risk/rules?reason=${encodeURIComponent(reasonFilter)}`)}
              disabled={!reasonFilter}
            >
              Найти правила
            </button>
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

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Распределение по уровням риска</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 8 }}>
          {RISK_LEVELS.map((level) => {
            const count = totals.counts[level] || 0;
            const percent = totals.total ? Math.round((count / totals.total) * 100) : 0;
            return (
              <div key={level} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div style={{ minWidth: 90 }}>
                  <RiskBadge level={level} />
                </div>
                <div style={{ flex: 1, background: "#e2e8f0", borderRadius: 4, height: 10, overflow: "hidden" }}>
                  <div
                    style={{
                      width: `${percent}%`,
                      height: "100%",
                      background: "linear-gradient(90deg, #10b981, #f97316, #ef4444)",
                      transition: "width 0.2s ease",
                    }}
                  />
                </div>
                <span style={{ minWidth: 80, textAlign: "right", color: "#334155" }}>
                  {count} / {percent}%
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <h2>Топ рискованных операций</h2>
      <Suspense fallback={<Loader label="Загружаем операции" />}>
        <Table
          columns={columns}
          data={topByRiskScore.slice(0, 50)}
          onRowClick={(row) => navigate(`/operations/${row.operation_id}`)}
        />
      </Suspense>

      <h2 style={{ marginTop: 16 }}>Последние high-risk / declines</h2>
      <Suspense fallback={<Loader label="Загружаем операции" />}>
        <Table
          columns={columns}
          data={highRiskOperations.slice(0, 30)}
          onRowClick={(row) => navigate(`/operations/${row.operation_id}`)}
        />
      </Suspense>
    </div>
  );
};

export default RiskAnalyticsPage;
