import React, { Suspense, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchOperations } from "../api/operations";
import { StatusBadge } from "../components/StatusBadge/StatusBadge";
import { Pagination } from "../components/Pagination/Pagination";
import { formatAmount, formatDateTime } from "../utils/format";
import { Operation } from "../types/operations";
import { Loader } from "../components/Loader/Loader";

const Table = React.lazy(() => import("../components/Table/Table").then((mod) => ({ default: mod.Table })));

export const OperationsListPage: React.FC = () => {
  const [limit, setLimit] = useState<number>(20);
  const [offset, setOffset] = useState<number>(0);
  const navigate = useNavigate();

  const filters = useMemo(() => ({ limit, offset }), [limit, offset]);

  const { data, isLoading, error, isFetching } = useQuery({
    queryKey: ["operations", filters],
    queryFn: () => fetchOperations(filters),
    staleTime: 30_000,
    refetchOnMount: false,
    placeholderData: (previousData) => previousData,
  });

  const operations = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div>
      <div className="page-header">
        <h1>Журнал операций</h1>
        {(isLoading || isFetching) && <Loader label="Обновляем операции" />}
        {error && <span style={{ color: "#dc2626" }}>{error.message}</span>}
      </div>

      <Suspense fallback={<Loader label="Загружаем таблицу" />}>
        <Table<Operation>
          columns={[
            { key: "created_at", title: "Дата", render: (row) => formatDateTime(row.created_at) },
            { key: "operation_type", title: "Тип", render: (row) => row.operation_type },
            { key: "status", title: "Статус", render: (row) => <StatusBadge status={row.status} /> },
            { key: "amount", title: "Сумма", render: (row) => `${formatAmount(row.amount)} ${row.currency}` },
            { key: "client_id", title: "Клиент", render: (row) => row.client_id },
            { key: "card_id", title: "Карта", render: (row) => row.card_id },
            { key: "merchant_id", title: "Мерчант", render: (row) => row.merchant_id },
            { key: "terminal_id", title: "Терминал", render: (row) => row.terminal_id },
          ]}
          data={operations}
          onRowClick={(row) => navigate(`/operations/${row.operation_id}`)}
        />
      </Suspense>

      <div style={{ marginTop: 12 }}>
        <Pagination total={total} limit={limit} offset={offset} onChange={setOffset} />
      </div>
    </div>
  );
};

export default OperationsListPage;
