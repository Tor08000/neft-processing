import React, { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { approvePaymentIntake, fetchPaymentIntakes, rejectPaymentIntake } from "../../api/finance";
import type { PaymentIntakeDetail } from "../../types/finance";
import { Table, type Column } from "../../components/Table/Table";
import { Pagination } from "../../components/Pagination/Pagination";
import { Loader } from "../../components/Loader/Loader";
import AdminWriteActionModal from "../../components/admin/AdminWriteActionModal";
import { useToast } from "../../components/Toast/useToast";
import { Toast } from "../../components/Toast/Toast";
import { extractRequestId } from "../ops/opsUtils";
import { useAdmin } from "../../admin/AdminContext";

type IntakeAction = { type: "approve" | "reject"; intake: PaymentIntakeDetail } | null;

export const PaymentIntakesPage: React.FC = () => {
  const { toast, showToast } = useToast();
  const { profile } = useAdmin();
  const [limit] = useState(50);
  const [offset, setOffset] = useState(0);
  const [status, setStatus] = useState("");
  const [debouncedStatus, setDebouncedStatus] = useState("");
  const [action, setAction] = useState<IntakeAction>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const canWrite = Boolean(profile?.permissions.finance?.write) && !profile?.read_only;

  useEffect(() => {
    const handler = window.setTimeout(() => setDebouncedStatus(status), 400);
    return () => window.clearTimeout(handler);
  }, [status]);

  const filters = useMemo(
    () => ({
      status: debouncedStatus || undefined,
      limit,
      offset,
    }),
    [debouncedStatus, limit, offset],
  );

  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ["payment-intakes", filters],
    queryFn: () => fetchPaymentIntakes(filters),
    staleTime: 20_000,
    placeholderData: (prev) => prev,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const requestId = errorMessage ? extractRequestId(new Error(errorMessage)) : null;

  const columns: Column<PaymentIntakeDetail>[] = [
    { key: "id", title: "ID", render: (row) => row.id },
    { key: "status", title: "Status", render: (row) => row.status },
    {
      key: "amount",
      title: "Amount",
      render: (row) => `${row.amount} ${row.currency}`,
    },
    { key: "invoice", title: "Invoice", render: (row) => row.invoice_id },
    { key: "org", title: "Org", render: (row) => row.org_id },
    {
      key: "proof",
      title: "Proof",
      render: (row) =>
        row.proof_url ? (
          <a href={row.proof_url} target="_blank" rel="noreferrer">
            Download
          </a>
        ) : (
          "—"
        ),
    },
    {
      key: "actions",
      title: "Actions",
      render: (row) => (
        <div style={{ display: "flex", gap: 8 }}>
          <button
            type="button"
            className="ghost"
            onClick={() => setAction({ type: "approve", intake: row })}
            disabled={!canWrite}
          >
            Approve
          </button>
          <button
            type="button"
            className="ghost"
            onClick={() => setAction({ type: "reject", intake: row })}
            disabled={!canWrite}
          >
            Reject
          </button>
        </div>
      ),
    },
  ];

  const handleConfirm = async ({ reason, correlationId }: { reason: string; correlationId: string }) => {
    if (!action) return;
    if (!canWrite) return;
    try {
      if (action.type === "approve") {
        await approvePaymentIntake(action.intake.id, { reason, correlation_id: correlationId });
      } else {
        await rejectPaymentIntake(action.intake.id, { reason, correlation_id: correlationId });
      }
      setAction(null);
      setErrorMessage(null);
      showToast("success", "Action completed");
      await refetch();
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setErrorMessage(message);
      showToast("error", "Failed to apply action");
    }
  };

  return (
    <div className="stack">
      <div className="page-header">
        <h1>Payment intakes</h1>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button type="button" className="ghost" onClick={() => refetch()}>
            Refresh
          </button>
          {(isLoading || isFetching) && <Loader label="Loading intakes" />}
        </div>
      </div>

      <div className="card" style={{ display: "flex", gap: 12 }}>
        <div className="filter">
          <span className="label">Status</span>
          <input placeholder="status" value={status} onChange={(event) => setStatus(event.target.value)} />
        </div>
      </div>

      {error ? (
        <div style={{ color: "#dc2626" }}>
          {(error as Error).message}
          {extractRequestId(error) ? <div style={{ marginTop: 4 }}>Request ID: {extractRequestId(error)}</div> : null}
        </div>
      ) : null}
      {errorMessage ? (
        <div style={{ color: "#dc2626" }}>
          {errorMessage}
          {requestId ? <div style={{ marginTop: 4 }}>Request ID: {requestId}</div> : null}
        </div>
      ) : null}

      <Table columns={columns} data={items} loading={isLoading} />
      <Pagination total={total} limit={limit} offset={offset} onChange={(value) => setOffset(value)} />
      {!canWrite ? <div className="muted">Read-only mode enabled</div> : null}

      <AdminWriteActionModal
        isOpen={action !== null}
        title={action?.type === "approve" ? "Approve payment intake" : "Reject payment intake"}
        requirePhrase
        confirmPhrase="CONFIRM"
        onConfirm={handleConfirm}
        onCancel={() => setAction(null)}
      />

      <Toast toast={toast} />
    </div>
  );
};

export default PaymentIntakesPage;
