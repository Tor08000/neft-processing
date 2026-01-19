import React from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listImports } from "../../api/reconciliation";
import type { ReconciliationImport } from "../../types/reconciliationImports";
import { Table, type Column } from "../../components/Table/Table";
import { Loader } from "../../components/Loader/Loader";
import { extractRequestId } from "../ops/opsUtils";

export const ReconciliationImportsPage: React.FC = () => {
  const navigate = useNavigate();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["reconciliation-imports"],
    queryFn: () => listImports(),
  });

  const items = data?.items ?? [];

  const columns: Column<ReconciliationImport>[] = [
    { key: "id", title: "Import ID", render: (row) => row.id },
    { key: "status", title: "Status", render: (row) => row.status },
    {
      key: "period",
      title: "Period",
      render: (row) =>
        row.period_from || row.period_to ? `${row.period_from ?? "—"} → ${row.period_to ?? "—"}` : "—",
    },
    { key: "uploaded", title: "Uploaded", render: (row) => row.uploaded_at },
    { key: "format", title: "Format", render: (row) => row.format },
  ];

  return (
    <div className="stack">
      <div className="page-header">
        <h1>Reconciliation imports</h1>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button type="button" className="ghost" onClick={() => refetch()}>
            Refresh
          </button>
          {isLoading && <Loader label="Loading imports" />}
        </div>
      </div>

      {error ? (
        <div style={{ color: "#dc2626" }}>
          {(error as Error).message}
          {extractRequestId(error) ? <div style={{ marginTop: 4 }}>Request ID: {extractRequestId(error)}</div> : null}
        </div>
      ) : null}

      <Table columns={columns} data={items} loading={isLoading} onRowClick={(row) => navigate(`/finance/reconciliation/imports/${row.id}`)} />
    </div>
  );
};

export default ReconciliationImportsPage;
