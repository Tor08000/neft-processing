import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchOperations } from "../api/operations";
import { UnauthorizedError } from "../api/client";
import { Table } from "../components/Table/Table";
import { StatusBadge } from "../components/StatusBadge/StatusBadge";
import { Pagination } from "../components/Pagination/Pagination";
import { formatAmount, formatDateTime } from "../utils/format";
import { Operation } from "../types/operations";
import { useAuth } from "../auth/AuthContext";

export const OperationsListPage: React.FC = () => {
  const [data, setData] = useState<Operation[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [limit, setLimit] = useState<number>(20);
  const [offset, setOffset] = useState<number>(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const navigate = useNavigate();
  const { clearToken } = useAuth();

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetchOperations({
          limit,
          offset,
        });
        setData(res.items);
        setTotal(res.total);
      } catch (err: any) {
        if (err instanceof UnauthorizedError) {
          clearToken();
          navigate("/login");
          return;
        }
        setError(err?.message ?? "Не удалось загрузить операции");
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, [limit, offset, navigate, clearToken]);

  return (
    <div>
      <div className="page-header">
        <h1>Журнал операций</h1>
        {loading && <span>Loading...</span>}
        {error && <span style={{ color: "#dc2626" }}>{error}</span>}
      </div>

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
        data={data}
        onRowClick={(row) => navigate(`/operations/${row.operation_id}`)}
      />

      <div style={{ marginTop: 12 }}>
        <Pagination total={total} limit={limit} offset={offset} onChange={setOffset} />
      </div>
    </div>
  );
};
