import React, { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  fetchPayoutBatchDetails,
  markPayoutSent,
  markPayoutSettled,
  reconcilePayoutBatch,
} from "../../api/payouts";
import { Loader } from "../../components/Loader/Loader";
import { PayoutStateBadge } from "../../components/PayoutStateBadge/PayoutStateBadge";
import { CopyButton } from "../../components/CopyButton/CopyButton";
import { ReconcilePanel } from "../../components/Payouts/ReconcilePanel";
import { MarkSentModal } from "../../components/Payouts/MarkSentModal";
import { MarkSettledModal } from "../../components/Payouts/MarkSettledModal";
import { Table, type Column } from "../../components/Table/Table";
import { Toast } from "../../components/Toast/Toast";
import { useToast } from "../../components/Toast/useToast";
import { PayoutBatchItem, PayoutReconcileResult } from "../../types/payouts";
import { formatDate, formatDateTime, formatQty, formatRub } from "../../utils/format";

function getErrorMessage(error: Error): string {
  if (error.message.includes("409")) {
    return "уже отправлено / ref конфликтует";
  }
  if (error.message.includes("400")) {
    return "нельзя из текущего статуса";
  }
  return error.message;
}

export const PayoutBatchDetail: React.FC = () => {
  const { batchId } = useParams();
  const navigate = useNavigate();
  const { toast, showToast } = useToast();
  const [isSentOpen, setSentOpen] = useState(false);
  const [isSettledOpen, setSettledOpen] = useState(false);
  const [reconcileData, setReconcileData] = useState<PayoutReconcileResult | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["payout-batch", batchId],
    queryFn: () => fetchPayoutBatchDetails(batchId ?? ""),
    enabled: Boolean(batchId),
  });

  const reconcileMutation = useMutation({
    mutationFn: () => reconcilePayoutBatch(batchId ?? ""),
    onSuccess: (result) => {
      setReconcileData(result);
      showToast("success", result.status === "OK" ? "Reconcile OK" : "Reconcile mismatch");
    },
    onError: (err: Error) => {
      showToast("error", err.message);
    },
  });

  const markSentMutation = useMutation({
    mutationFn: (payload: { provider: string; external_ref: string }) => markPayoutSent(batchId ?? "", payload),
    onSuccess: () => {
      setActionError(null);
      setSentOpen(false);
      showToast("success", "Batch marked as SENT");
      void refetch();
    },
    onError: (err: Error) => {
      setActionError(getErrorMessage(err));
      showToast("error", err.message);
    },
  });

  const markSettledMutation = useMutation({
    mutationFn: (payload: { provider: string; external_ref: string }) => markPayoutSettled(batchId ?? "", payload),
    onSuccess: () => {
      setActionError(null);
      setSettledOpen(false);
      showToast("success", "Batch marked as SETTLED");
      void refetch();
    },
    onError: (err: Error) => {
      setActionError(getErrorMessage(err));
      showToast("error", err.message);
    },
  });

  const batch = data ?? null;
  const items = data?.items ?? [];

  const summaryRows = useMemo(() => {
    if (!batch) return [];
    return [
      { label: "Partner", value: batch.partner_id },
      { label: "Period", value: `${formatDate(batch.date_from)} – ${formatDate(batch.date_to)}` },
      { label: "State", value: <PayoutStateBadge state={batch.state} /> },
      { label: "Total amount", value: formatRub(batch.total_amount) },
      { label: "Total qty", value: formatQty(batch.total_qty) },
      { label: "Operations count", value: batch.operations_count },
      { label: "Provider", value: batch.provider ?? "-" },
      {
        label: "External ref",
        value: batch.external_ref ? (
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span>{batch.external_ref}</span>
            <CopyButton
              value={batch.external_ref}
              label="Copy"
              onCopy={() => showToast("success", "External ref copied")}
            />
          </div>
        ) : (
          "-"
        ),
      },
      { label: "Created at", value: formatDateTime(batch.created_at) },
      { label: "Sent at", value: formatDateTime(batch.sent_at) },
      { label: "Settled at", value: formatDateTime(batch.settled_at) },
    ];
  }, [batch, showToast]);

  const columns: Column<PayoutBatchItem>[] = [
    { key: "id", title: "Item ID", render: (row) => row.id.slice(0, 8) },
    {
      key: "azs",
      title: "AZS/Product",
      render: (row) => [row.azs_id, row.product_id].filter(Boolean).join(" / ") || "-",
    },
    { key: "qty", title: "Qty", render: (row) => formatQty(row.qty) },
    { key: "amount_gross", title: "Amount gross", render: (row) => formatRub(row.amount_gross) },
    { key: "commission_amount", title: "Commission", render: (row) => formatRub(row.commission_amount) },
    { key: "amount_net", title: "Amount net", render: (row) => formatRub(row.amount_net) },
    { key: "operations_count", title: "Operations", render: (row) => row.operations_count ?? "-" },
  ];

  if (isLoading) {
    return <Loader label="Loading payout batch" />;
  }

  if (error || !batch) {
    return (
      <div className="card">
        <p style={{ color: "#dc2626", fontWeight: 600 }}>Failed to load batch</p>
        <button type="button" className="ghost neft-btn-secondary" onClick={() => refetch()}>
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="stack">
      <div className="page-header">
        <div>
          <button type="button" className="ghost neft-btn-secondary" onClick={() => navigate(-1)}>
            ← Back
          </button>
          <h1 style={{ marginTop: 8 }}>Payout batch {batch.id.slice(0, 8)}</h1>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <CopyButton value={batch.id} label="Copy batch id" onCopy={() => showToast("success", "Batch ID copied")} />
          <button
            type="button"
            className="button neft-btn-secondary"
            onClick={() => reconcileMutation.mutate()}
            disabled={reconcileMutation.isPending}
          >
            Reconcile
          </button>
          <button
            type="button"
            className="button neft-btn-secondary"
            onClick={() => {
              setActionError(null);
              setSentOpen(true);
            }}
            disabled={batch.state !== "READY"}
          >
            Mark sent
          </button>
          <button
            type="button"
            className="button neft-btn-secondary"
            onClick={() => {
              setActionError(null);
              setSettledOpen(true);
            }}
            disabled={batch.state !== "SENT"}
          >
            Mark settled
          </button>
        </div>
      </div>

      <div className="card-grid">
        <div className="card">
          <h3>Summary</h3>
          <div style={{ display: "grid", gap: 8, marginTop: 12 }}>
            {summaryRows.map((row) => (
              <div key={row.label} style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <span style={{ color: "#64748b", fontWeight: 600 }}>{row.label}</span>
                <span>{row.value}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="card">
          <h3>Actions</h3>
          <p style={{ color: "#475569", marginBottom: 12 }}>Use actions to update the payout state.</p>
          <div className="stack">
            <button
              type="button"
              className="button neft-btn-secondary"
              onClick={() => reconcileMutation.mutate()}
              disabled={reconcileMutation.isPending}
            >
              Reconcile
            </button>
            <button
              type="button"
              className="button neft-btn-secondary"
              onClick={() => {
                setActionError(null);
                setSentOpen(true);
              }}
              disabled={batch.state !== "READY"}
            >
              Mark sent
            </button>
            <button
              type="button"
              className="button neft-btn-secondary"
              onClick={() => {
                setActionError(null);
                setSettledOpen(true);
              }}
              disabled={batch.state !== "SENT"}
            >
              Mark settled
            </button>
          </div>
        </div>
      </div>

      <ReconcilePanel data={reconcileData} onCopyDiagnostics={() => showToast("success", "Diagnostics copied")} />

      <div>
        <h3>Items</h3>
        <Table
          columns={columns}
          data={items}
          emptyState={{
            title: "Нет позиций",
            description: "В этом батче пока нет операций.",
            actionLabel: "Обновить",
            actionOnClick: () => refetch(),
          }}
        />
      </div>

      <MarkSentModal
        isOpen={isSentOpen}
        onClose={() => setSentOpen(false)}
        onConfirm={(payload) => markSentMutation.mutate(payload)}
        isSubmitting={markSentMutation.isPending}
        error={actionError}
      />
      <MarkSettledModal
        isOpen={isSettledOpen}
        onClose={() => setSettledOpen(false)}
        onConfirm={(payload) => markSettledMutation.mutate(payload)}
        isSubmitting={markSettledMutation.isPending}
        error={actionError}
        defaultProvider={batch.provider ?? undefined}
        defaultExternalRef={batch.external_ref ?? undefined}
      />
      <Toast toast={toast} />
    </div>
  );
};

export default PayoutBatchDetail;
