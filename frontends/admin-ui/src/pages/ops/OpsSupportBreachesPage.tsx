import React, { useEffect, useState } from "react";
import { fetchOpsSupportBreaches } from "../../api/ops";
import type { OpsSupportBreachItem } from "../../types/ops";
import { Table, type Column } from "../../components/Table/Table";
import { formatDateTime } from "../../utils/format";
import { extractRequestId } from "./opsUtils";

export const OpsSupportBreachesPage: React.FC = () => {
  const [items, setItems] = useState<OpsSupportBreachItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    setLoading(true);
    fetchOpsSupportBreaches()
      .then((data) => {
        setItems(data.items ?? []);
        setError(null);
      })
      .catch((err: Error) => setError(err))
      .finally(() => setLoading(false));
  }, []);

  const requestId = error ? extractRequestId(error) : null;

  const columns: Column<OpsSupportBreachItem>[] = [
    { key: "id", title: "ID", render: (row) => row.id },
    { key: "status", title: "Status", render: (row) => row.status },
    { key: "priority", title: "Priority", render: (row) => row.priority },
    { key: "created", title: "Created", render: (row) => formatDateTime(row.created_at) },
    { key: "sla_first", title: "SLA first response", render: (row) => row.sla_first_response_status },
    { key: "sla_resolution", title: "SLA resolution", render: (row) => row.sla_resolution_status },
  ];

  return (
    <div>
      <h1>Support SLA breaches</h1>
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

export default OpsSupportBreachesPage;
