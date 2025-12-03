import React, { Suspense, useMemo } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchOperation, fetchOperationChildren } from "../api/operations";
import { StatusBadge } from "../components/StatusBadge/StatusBadge";
import { Table, type Column } from "../components/Table/Table";
import { formatAmount, formatDateTime } from "../utils/format";
import { Operation } from "../types/operations";
import { Loader } from "../components/Loader/Loader";

export const OperationDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { data: operation, error, isLoading, isFetching } = useQuery({
    queryKey: ["operations", id],
    queryFn: () => fetchOperation(id as string),
    enabled: Boolean(id),
    staleTime: 30_000,
  });

  const { data: children = [], isFetching: isChildrenFetching } = useQuery({
    queryKey: ["operations", id, "children"],
    queryFn: () => fetchOperationChildren(id as string),
    enabled: Boolean(id),
    staleTime: 30_000,
  });

  const totals = useMemo(() => {
    const captured = children
      .filter((op) => op.operation_type === "CAPTURE")
      .reduce((acc, op) => acc + op.amount, 0);
    const refunded = children
      .filter((op) => op.operation_type === "REFUND")
      .reduce((acc, op) => acc + op.amount, 0);
    const authAmount = operation?.amount ?? 0;
    return {
      authAmount,
      captured,
      refunded,
      remaining: authAmount - captured + refunded,
    };
  }, [children, operation]);

  const columns: Column<Operation>[] = [
    { key: "id", title: "ID", render: (row) => row.operation_id },
    { key: "type", title: "Type", render: (row) => row.operation_type },
    { key: "status", title: "Status", render: (row) => <StatusBadge status={row.status} /> },
    { key: "amount", title: "Amount", render: (row) => formatAmount(row.amount) },
    { key: "created", title: "Created", render: (row) => formatDateTime(row.created_at) },
  ];

  return (
    <div>
      <div className="page-header">
        <h1>Operation details</h1>
        {(isLoading || isFetching || isChildrenFetching) && <Loader label="Загружаем операцию" />}
        {error && <span style={{ color: "#dc2626" }}>{error.message}</span>}
      </div>

      {operation && (
        <div className="card-grid" style={{ marginBottom: 16 }}>
          <div className="card">
            <h3>{operation.operation_id}</h3>
            <p>
              <strong>Type:</strong> {operation.operation_type}
            </p>
            <p>
              <strong>Status:</strong> <StatusBadge status={operation.status} />
            </p>
            <p>
              <strong>Amount:</strong> {formatAmount(operation.amount)}
            </p>
            <p>
              <strong>Created:</strong> {formatDateTime(operation.created_at)}
            </p>
            <p>
              <strong>Merchant:</strong> {operation.merchant_id}
            </p>
          </div>
          <div className="card">
            <h3>Aggregates</h3>
            <p>
              AUTH: <strong>{formatAmount(totals.authAmount)}</strong>
            </p>
            <p>
              Captured: <strong>{formatAmount(totals.captured)}</strong>
            </p>
            <p>
              Refunded: <strong>{formatAmount(totals.refunded)}</strong>
            </p>
            <p>
              Remaining: <strong>{formatAmount(totals.remaining)}</strong>
            </p>
          </div>
        </div>
      )}

      <h2>Child operations</h2>
      <Suspense fallback={<Loader label="Загружаем операции" />}>
        <Table columns={columns} data={children} />
      </Suspense>
    </div>
  );
};

export default OperationDetailsPage;
