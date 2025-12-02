import React, { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchOperation, fetchOperationChildren } from "../api/operations";
import { StatusBadge } from "../components/StatusBadge/StatusBadge";
import { Table } from "../components/Table/Table";
import { formatAmount, formatDateTime } from "../utils/format";
import { Operation } from "../types/operations";

export const OperationDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [operation, setOperation] = useState<Operation | null>(null);
  const [children, setChildren] = useState<Operation[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    const load = async () => {
      try {
        const [op, child] = await Promise.all([fetchOperation(id), fetchOperationChildren(id)]);
        setOperation(op);
        setChildren(child);
      } catch (err: any) {
        setError(err?.message ?? "Не удалось загрузить операцию");
      }
    };

    void load();
  }, [id]);

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

  return (
    <div>
      <div className="page-header">
        <h1>Operation details</h1>
        {error && <span style={{ color: "#dc2626" }}>{error}</span>}
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
      <Table<Operation>
        columns={[
          { key: "id", title: "ID", render: (row) => row.operation_id },
          { key: "type", title: "Type", render: (row) => row.operation_type },
          { key: "status", title: "Status", render: (row) => <StatusBadge status={row.status} /> },
          { key: "amount", title: "Amount", render: (row) => formatAmount(row.amount) },
          { key: "created", title: "Created", render: (row) => formatDateTime(row.created_at) },
        ]}
        data={children}
      />
    </div>
  );
};
