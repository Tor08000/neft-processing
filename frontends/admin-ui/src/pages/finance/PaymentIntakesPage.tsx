import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { approvePaymentIntake, fetchPaymentIntake, fetchPaymentIntakes, rejectPaymentIntake } from "../../api/finance";
import type { PaymentIntakeDetail } from "../../types/finance";
import { Table, type Column } from "../../components/Table/Table";
import { Pagination } from "../../components/Pagination/Pagination";
import { Loader } from "../../components/Loader/Loader";
import AdminWriteActionModal from "../../components/admin/AdminWriteActionModal";
import { useToast } from "../../components/Toast/useToast";
import { Toast } from "../../components/Toast/Toast";
import { EmptyState } from "../../components/common/EmptyState";
import { ErrorState } from "../../components/common/ErrorState";
import { extractRequestId } from "../ops/opsUtils";
import { useAdmin } from "../../admin/AdminContext";
import { DetailPanel } from "@shared/brand/components";

type IntakeAction = { type: "approve" | "reject"; intake: PaymentIntakeDetail } | null;

export const PaymentIntakesPage: React.FC = () => {
  const { toast, showToast } = useToast();
  const { profile } = useAdmin();
  const [limit] = useState(50);
  const [offset, setOffset] = useState(0);
  const [status, setStatus] = useState("");
  const [debouncedStatus, setDebouncedStatus] = useState("");
  const [action, setAction] = useState<IntakeAction>(null);
  const [selectedIntakeId, setSelectedIntakeId] = useState<number | null>(null);
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

  const { data: selectedIntake, isFetching: isFetchingSelected } = useQuery({
    queryKey: ["payment-intake-detail", selectedIntakeId],
    queryFn: () => fetchPaymentIntake(selectedIntakeId as number),
    enabled: selectedIntakeId !== null,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const requestId = errorMessage ? extractRequestId(new Error(errorMessage)) : null;
  const hasActiveFilters = Boolean(status.trim());

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
        <div className="table-row-actions">
          <button type="button" className="ghost" onClick={() => setSelectedIntakeId(row.id)}>
            Details
          </button>
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
        <div className="toolbar-actions">
          <button type="button" className="ghost" onClick={() => refetch()}>
            Refresh
          </button>
          {selectedIntakeId !== null ? (
            <button type="button" className="ghost" onClick={() => setSelectedIntakeId(null)}>
              Hide details
            </button>
          ) : null}
          {(isLoading || isFetching) && <Loader label="Loading intakes" />}
        </div>
      </div>

      <Table
        columns={columns}
        data={items}
        loading={isLoading}
        toolbar={
          <div className="filters">
            <div className="filter">
              <span className="label">Status</span>
              <input
                placeholder="status"
                value={status}
                onChange={(event) => {
                  setStatus(event.target.value);
                  setOffset(0);
                }}
              />
            </div>
          </div>
        }
        errorState={
          error
            ? {
                title: "Failed to load payment intakes",
                description: (error as Error).message,
                actionLabel: "Retry",
                actionOnClick: () => refetch(),
                requestId: extractRequestId(error),
              }
            : undefined
        }
        emptyState={{
          title: hasActiveFilters ? "No payment intakes for current filters" : "No payment intakes yet",
          description: hasActiveFilters
            ? "Adjust the status filter or reset it to return to the full review queue."
            : "Submitted payment confirmations will appear here for finance review.",
          primaryAction: hasActiveFilters
            ? {
                label: "Reset filters",
                onClick: () => {
                  setStatus("");
                  setOffset(0);
                },
              }
            : {
                label: "Refresh",
                onClick: () => refetch(),
              },
        }}
        footer={
          <div className="table-footer__content">
            <span className="muted">Visible intakes: {items.length} / {total}</span>
            <Pagination total={total} limit={limit} offset={offset} onChange={(value) => setOffset(value)} />
          </div>
        }
      />
      {!canWrite ? <div className="muted">Read-only mode enabled</div> : null}

      <DetailPanel
        open={selectedIntakeId !== null}
        title="Selected intake"
        subtitle={selectedIntake ? `Intake ${selectedIntake.id}` : "Loading intake detail"}
        onClose={() => setSelectedIntakeId(null)}
        closeLabel="Close"
        size="md"
      >
        {isFetchingSelected && !selectedIntake ? (
          <Loader label="Loading intake detail" />
        ) : selectedIntake ? (
          <div className="stack">
            <div className="detail-panel__card" style={{ display: "grid", gap: 6 }}>
              <div>ID: {selectedIntake.id}</div>
              <div>Status: {selectedIntake.status}</div>
              <div>
                Amount: {selectedIntake.amount} {selectedIntake.currency}
              </div>
              <div>Invoice status: {selectedIntake.invoice_status ?? "—"}</div>
              <div>
                Invoice:{" "}
                {selectedIntake.invoice_link ? (
                  <Link to={selectedIntake.invoice_link}>{selectedIntake.invoice_id}</Link>
                ) : (
                  selectedIntake.invoice_id
                )}
              </div>
              <div>Reviewer: {selectedIntake.reviewed_by_admin ?? "—"}</div>
              <div>Review note: {selectedIntake.review_note ?? "—"}</div>
            </div>
            <div className="detail-panel__card">
              <strong>Timeline</strong>
              {selectedIntake.timeline?.length ? (
                <ul className="timeline">
                  {selectedIntake.timeline.map((event) => (
                    <li key={`${event.entity_type}-${event.entity_id}-${event.event_type}-${event.ts ?? "ts"}`}>
                      <span className="timeline__marker" />
                      <div className="timeline-item">
                        <div className="timeline-item__title">{event.event_type}</div>
                        <div className="timeline-item__refs">
                          {event.ts ? <span>{event.ts}</span> : null}
                          {event.reason ? <span>reason: {event.reason}</span> : null}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState
                  title="No timeline events yet"
                  description="Review actions and reconciliation events will appear here."
                />
              )}
            </div>
          </div>
        ) : (
          <EmptyState
            title="Intake details unavailable"
            description="Refresh the queue and reopen the intake to retry."
            primaryAction={{ label: "Refresh queue", onClick: () => refetch() }}
          />
        )}
      </DetailPanel>

      <AdminWriteActionModal
        isOpen={action !== null}
        title={action?.type === "approve" ? "Approve payment intake" : "Reject payment intake"}
        requirePhrase
        confirmPhrase="CONFIRM"
        onConfirm={handleConfirm}
        onCancel={() => setAction(null)}
      />

      {errorMessage ? (
        <ErrorState
          title="Failed to apply payment intake action"
          description={errorMessage}
          requestId={requestId}
        />
      ) : null}

      <Toast toast={toast} />
    </div>
  );
};

export default PaymentIntakesPage;
