import React, { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { approvePayout, fetchPayoutDetail, markPayoutPaid, rejectPayout } from "../../api/finance";
import AdminWriteActionModal from "../../components/admin/AdminWriteActionModal";
import BlockersPanel from "../../components/finance/BlockersPanel";
import { Loader } from "../../components/Loader/Loader";
import { useToast } from "../../components/Toast/useToast";
import { Toast } from "../../components/Toast/Toast";
import { extractRequestId } from "../ops/opsUtils";

type ActionType = "approve" | "reject" | "mark-paid" | null;

export const PayoutDetailsPage: React.FC = () => {
  const { payoutId } = useParams();
  const { toast, showToast } = useToast();
  const [action, setAction] = useState<ActionType>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["payout-detail", payoutId],
    queryFn: () => fetchPayoutDetail(payoutId || ""),
    enabled: Boolean(payoutId),
  });

  const requestId = useMemo(() => (errorMessage ? extractRequestId(new Error(errorMessage)) : null), [errorMessage]);

  const handleConfirm = async ({ reason }: { reason: string }) => {
    if (!payoutId) return;
    try {
      if (action === "approve") {
        await approvePayout(payoutId, reason);
      } else if (action === "reject") {
        await rejectPayout(payoutId, reason);
      } else if (action === "mark-paid") {
        await markPayoutPaid(payoutId, reason);
      }
      setAction(null);
      setErrorMessage(null);
      showToast("success", "Action completed");
      await refetch();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      setErrorMessage(message);
      showToast("error", "Failed to apply action");
    }
  };

  if (isLoading) {
    return <Loader label="Loading payout" />;
  }

  if (!data) {
    return <div>Payout not found.</div>;
  }

  return (
    <div className="stack">
      <div className="page-header">
        <h1>Payout {data.payout_id}</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <button type="button" className="ghost" onClick={() => refetch()}>
            Refresh
          </button>
        </div>
      </div>

      {errorMessage ? (
        <div style={{ color: "#dc2626" }}>
          {errorMessage}
          {requestId ? <div style={{ marginTop: 4 }}>Request ID: {requestId}</div> : null}
        </div>
      ) : null}

      <div className="card">
        <div>Status: {data.status}</div>
        <div>Partner org: {data.partner_org}</div>
        <div>
          Amount: {data.amount} {data.currency}
        </div>
        <div>Created: {data.created_at ?? "—"}</div>
        <div>Processed: {data.processed_at ?? "—"}</div>
      </div>

      <BlockersPanel blockers={data.blockers} title="Blockers" />

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Policy</h3>
        <div>Min payout: {data.policy?.min_payout_amount ?? "—"}</div>
        <div>Hold days: {data.policy?.payout_hold_days ?? "—"}</div>
        <div>Schedule: {data.policy?.payout_schedule ?? "—"}</div>
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Trace</h3>
        {data.trace?.length ? (
          <ul style={{ paddingLeft: 18, marginBottom: 0 }}>
            {data.trace.map((item) => (
              <li key={`${item.entity_type}-${item.entity_id}`}>
                {item.entity_type} · {item.entity_id} · {item.amount ?? "—"} {item.currency ?? ""}
              </li>
            ))}
          </ul>
        ) : (
          <div className="muted">No trace items.</div>
        )}
      </div>

      <div className="card" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button type="button" className="neft-btn" onClick={() => setAction("approve")}>
          Approve
        </button>
        <button type="button" className="neft-btn-secondary" onClick={() => setAction("mark-paid")}>
          Mark paid
        </button>
        <button type="button" className="ghost" onClick={() => setAction("reject")}>
          Reject
        </button>
      </div>

      <AdminWriteActionModal
        isOpen={action !== null}
        title="Confirm payout action"
        requirePhrase
        confirmPhrase="CONFIRM"
        onConfirm={handleConfirm}
        onCancel={() => setAction(null)}
      />

      <Toast message={toast.message} type={toast.type} visible={toast.visible} onDismiss={toast.onDismiss} />
    </div>
  );
};

export default PayoutDetailsPage;
