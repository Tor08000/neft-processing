import React, { useEffect, useState } from "react";
import { fetchOpsFailedImports } from "../../api/ops";
import type { OpsFailedReconciliationImport } from "../../types/ops";
import { Table, type Column } from "../../components/Table/Table";
import { formatDateTime } from "../../utils/format";
import { extractRequestId } from "./opsUtils";

export const OpsFailedImportsPage: React.FC = () => {
  const [items, setItems] = useState<OpsFailedReconciliationImport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    setLoading(true);
    fetchOpsFailedImports()
      .then((data) => {
        setItems(data.items ?? []);
        setError(null);
      })
      .catch((err: Error) => setError(err))
      .finally(() => setLoading(false));
  }, []);

  const requestId = error ? extractRequestId(error) : null;

  const columns: Column<OpsFailedReconciliationImport>[] = [
    { key: "id", title: "ID", render: (row) => row.id },
    { key: "status", title: "Status", render: (row) => row.status },
    { key: "uploaded", title: "Uploaded", render: (row) => formatDateTime(row.uploaded_at) },
    { key: "error", title: "Error", render: (row) => row.error ?? "—" },
  ];

  return (
    <div>
      <h1>Failed reconciliation imports</h1>
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

export default OpsFailedImportsPage;
