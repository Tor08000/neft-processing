import React, { useEffect, useState } from "react";
import { fetchOpsBlockedPayouts } from "../../api/ops";
import type { OpsBlockedPayoutItem } from "../../types/ops";
import { Table, type Column } from "../../components/Table/Table";
import { formatAmount, formatDateTime } from "../../utils/format";
import { extractRequestId } from "./opsUtils";

export const OpsBlockedPayoutsPage: React.FC = () => {
  const [items, setItems] = useState<OpsBlockedPayoutItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    setLoading(true);
    fetchOpsBlockedPayouts()
      .then((data) => {
        setItems(data.items ?? []);
        setError(null);
      })
      .catch((err: Error) => setError(err))
      .finally(() => setLoading(false));
  }, []);

  const requestId = error ? extractRequestId(error) : null;

  const columns: Column<OpsBlockedPayoutItem>[] = [
    { key: "id", title: "ID", render: (row) => row.id },
    { key: "settlement", title: "Settlement", render: (row) => row.settlement_id },
    { key: "status", title: "Status", render: (row) => row.status },
    { key: "amount", title: "Amount", render: (row) => formatAmount(row.amount) },
    { key: "currency", title: "Currency", render: (row) => row.currency },
    { key: "created", title: "Created", render: (row) => formatDateTime(row.created_at) },
    { key: "error", title: "Error", render: (row) => row.error ?? "—" },
  ];

  return (
    <div>
      <h1>Blocked payouts</h1>
      {error ? (
        <div style={{ color: "#dc2626", marginBottom: 12 }}>
          {error.message}
          {requestId ? <div style={{ marginTop: 4 }}>Request ID: {requestId}</div> : null}
        </div>
      ) : null}
      <Table
        columns={columns}
        data={items}
        loading={loading}
        emptyMessage="No issues detected"
        skeletonRows={5}
      />
    </div>
  );
};

export default OpsBlockedPayoutsPage;
