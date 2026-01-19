import React, { useEffect, useState } from "react";
import { fetchOpsFailedExports } from "../../api/ops";
import type { OpsFailedExportItem } from "../../types/ops";
import { Table, type Column } from "../../components/Table/Table";
import { formatDateTime } from "../../utils/format";
import { extractRequestId } from "./opsUtils";

export const OpsFailedExportsPage: React.FC = () => {
  const [items, setItems] = useState<OpsFailedExportItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    setLoading(true);
    fetchOpsFailedExports()
      .then((data) => {
        setItems(data.items ?? []);
        setError(null);
      })
      .catch((err: Error) => setError(err))
      .finally(() => setLoading(false));
  }, []);

  const requestId = error ? extractRequestId(error) : null;

  const columns: Column<OpsFailedExportItem>[] = [
    { key: "id", title: "ID", render: (row) => row.id },
    { key: "report_type", title: "Report", render: (row) => row.report_type },
    { key: "format", title: "Format", render: (row) => row.format },
    { key: "status", title: "Status", render: (row) => row.status },
    { key: "created", title: "Created", render: (row) => formatDateTime(row.created_at) },
    { key: "error", title: "Error", render: (row) => row.error_message ?? "—" },
  ];

  return (
    <div>
      <h1>Failed exports</h1>
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

export default OpsFailedExportsPage;
