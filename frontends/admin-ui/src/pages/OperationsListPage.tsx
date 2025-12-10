import React, { Suspense, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchOperations } from "../api/operations";
import { StatusBadge } from "../components/StatusBadge/StatusBadge";
import { RiskBadge } from "../components/RiskBadge/RiskBadge";
import { Pagination } from "../components/Pagination/Pagination";
import { Table, type Column } from "../components/Table/Table";
import { formatAmount, formatDateTime } from "../utils/format";
import { Operation, type OperationQuery } from "../types/operations";
import { Loader } from "../components/Loader/Loader";

export const OperationsListPage: React.FC = () => {
  const [limit, setLimit] = useState<number>(20);
  const [offset, setOffset] = useState<number>(0);
  const [riskLevel, setRiskLevel] = useState<string>("ANY");
  const [minScore, setMinScore] = useState<string>("");
  const [maxScore, setMaxScore] = useState<string>("");
  const [orderBy, setOrderBy] = useState<OperationQuery["order_by"]>("created_at_desc");
  const navigate = useNavigate();

  const filters = useMemo(
    () => ({
      limit,
      offset,
      order_by: orderBy,
      risk_result: riskLevel !== "ANY" ? riskLevel : undefined,
      risk_min_score: minScore !== "" ? Number(minScore) : undefined,
      risk_max_score: maxScore !== "" ? Number(maxScore) : undefined,
    }),
    [limit, maxScore, minScore, offset, orderBy, riskLevel],
  );

  const { data, isLoading, error, isFetching } = useQuery({
    queryKey: ["operations", filters],
    queryFn: () => fetchOperations(filters),
    staleTime: 30_000,
    refetchOnMount: false,
    placeholderData: (previousData) => previousData,
  });

  const operations = data?.items ?? [];
  const total = data?.total ?? 0;

  const columns: Column<Operation>[] = [
    { key: "created_at", title: "Дата", render: (row) => formatDateTime(row.created_at) },
    { key: "operation_type", title: "Тип", render: (row) => row.operation_type },
    { key: "status", title: "Статус", render: (row) => <StatusBadge status={row.status} /> },
    { key: "amount", title: "Сумма", render: (row) => `${formatAmount(row.amount)} ${row.currency}` },
    {
      key: "risk_result",
      title: "Риск",
      render: (row) => <RiskBadge level={row.risk_result} score={row.risk_score ?? undefined} />,
    },
    {
      key: "risk_score",
      title: "Score",
      render: (row) => (typeof row.risk_score === "number" ? (row.risk_score * 100).toFixed(0) : "—"),
    },
    { key: "client_id", title: "Клиент", render: (row) => row.client_id },
    { key: "card_id", title: "Карта", render: (row) => row.card_id },
    { key: "merchant_id", title: "Мерчант", render: (row) => row.merchant_id },
    { key: "terminal_id", title: "Терминал", render: (row) => row.terminal_id },
  ];

  return (
    <div>
      <div className="page-header">
        <h1>Журнал операций</h1>
        {(isLoading || isFetching) && <Loader label="Обновляем операции" />}
        {error && <span style={{ color: "#dc2626" }}>{error.message}</span>}
      </div>

      <div className="filters">
        <div className="filter">
          <span className="label">Риск</span>
          <select value={riskLevel} onChange={(e) => setRiskLevel(e.target.value)}>
            <option value="ANY">Любой</option>
            <option value="LOW">LOW</option>
            <option value="MEDIUM">MEDIUM</option>
            <option value="HIGH">HIGH</option>
            <option value="BLOCK">BLOCK</option>
          </select>
        </div>
        <div className="filter">
          <span className="label">Min score</span>
          <input
            type="number"
            step="0.01"
            min={0}
            max={1}
            value={minScore}
            onChange={(e) => setMinScore(e.target.value)}
            placeholder="0.0"
          />
        </div>
        <div className="filter">
          <span className="label">Max score</span>
          <input
            type="number"
            step="0.01"
            min={0}
            max={1}
            value={maxScore}
            onChange={(e) => setMaxScore(e.target.value)}
            placeholder="1.0"
          />
        </div>
        <div className="filter">
          <span className="label">Сортировка</span>
          <select
            value={orderBy}
            onChange={(e) => setOrderBy(e.target.value as OperationQuery["order_by"])}
          >
            <option value="created_at_desc">Новые сверху</option>
            <option value="created_at_asc">Старые сверху</option>
            <option value="amount_desc">Сумма по убыванию</option>
            <option value="amount_asc">Сумма по возрастанию</option>
            <option value="risk_score_desc">Высокий риск сверху</option>
            <option value="risk_score_asc">Низкий риск сверху</option>
          </select>
        </div>
      </div>

      <Suspense fallback={<Loader label="Загружаем таблицу" />}>
        <Table columns={columns} data={operations} onRowClick={(row) => navigate(`/operations/${row.operation_id}`)} />
      </Suspense>

      <div style={{ marginTop: 12 }}>
        <Pagination total={total} limit={limit} offset={offset} onChange={setOffset} />
      </div>
    </div>
  );
};

export default OperationsListPage;
