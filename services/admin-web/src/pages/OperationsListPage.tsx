import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchOperations } from "../api/operations";
import { Table } from "../components/Table/Table";
import { StatusBadge } from "../components/StatusBadge/StatusBadge";
import { Pagination } from "../components/Pagination/Pagination";
import { SelectFilter } from "../components/Filters/SelectFilter";
import { DateRangeFilter } from "../components/Filters/DateRangeFilter";
import { formatAmount, formatDateTime } from "../utils/format";
import { Operation } from "../types/operations";

export const OperationsListPage: React.FC = () => {
  const [data, setData] = useState<Operation[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [limit, setLimit] = useState<number>(20);
  const [offset, setOffset] = useState<number>(0);
  const [operationType, setOperationType] = useState<string>("");
  const [status, setStatus] = useState<string>("");
  const [merchantId, setMerchantId] = useState<string>("");
  const [dateRange, setDateRange] = useState<{ from?: string; to?: string }>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const navigate = useNavigate();

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetchOperations({
          limit,
          offset,
          operation_type: operationType || undefined,
          status: status || undefined,
          merchant_id: merchantId || undefined,
          date_from: dateRange.from,
          date_to: dateRange.to,
        });
        setData(res.items);
        setTotal(res.total);
      } catch (err: any) {
        setError(err?.message ?? "Не удалось загрузить операции");
      } finally {
        setLoading(false);
      }
    };

    void load();
  }, [limit, offset, operationType, status, merchantId, dateRange]);

  return (
    <div>
      <div className="page-header">
        <h1>Operations</h1>
        {loading && <span>Loading...</span>}
        {error && <span style={{ color: "#dc2626" }}>{error}</span>}
      </div>
      <div className="filters">
        <SelectFilter
          label="Type"
          value={operationType}
          onChange={(v) => {
            setOffset(0);
            setOperationType(v);
          }}
          options={[
            { value: "AUTH", label: "AUTH" },
            { value: "CAPTURE", label: "CAPTURE" },
            { value: "REFUND", label: "REFUND" },
            { value: "REVERSAL", label: "REVERSAL" },
          ]}
        />
        <SelectFilter
          label="Status"
          value={status}
          onChange={(v) => {
            setOffset(0);
            setStatus(v);
          }}
          options={[
            { value: "PENDING", label: "PENDING" },
            { value: "AUTHORIZED", label: "AUTHORIZED" },
            { value: "CAPTURED", label: "CAPTURED" },
            { value: "DECLINED", label: "DECLINED" },
          ]}
        />
        <div className="filter">
          <span className="label">Merchant</span>
          <input
            value={merchantId}
            onChange={(e) => {
              setMerchantId(e.target.value);
              setOffset(0);
            }}
            placeholder="merchant id"
          />
        </div>
        <DateRangeFilter
          label="Dates"
          from={dateRange.from}
          to={dateRange.to}
          onChange={(range) => {
            setDateRange(range);
            setOffset(0);
          }}
        />
        <div className="filter">
          <span className="label">Limit</span>
          <input type="number" value={limit} onChange={(e) => setLimit(Number(e.target.value) || 20)} />
        </div>
      </div>

      <Table<Operation>
        columns={[
          { key: "operation_id", title: "ID", render: (row) => row.operation_id },
          { key: "type", title: "Type", render: (row) => row.operation_type },
          { key: "status", title: "Status", render: (row) => <StatusBadge status={row.status} /> },
          { key: "merchant", title: "Merchant", render: (row) => row.merchant_id },
          { key: "terminal", title: "Terminal", render: (row) => row.terminal_id },
          { key: "client", title: "Client", render: (row) => row.client_id },
          { key: "card", title: "Card", render: (row) => row.card_id },
          { key: "amount", title: "Amount", render: (row) => formatAmount(row.amount) },
          { key: "created", title: "Created", render: (row) => formatDateTime(row.created_at) },
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
