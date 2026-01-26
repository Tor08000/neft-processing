import React, { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  approvePayout,
  fetchPartnerLedger,
  fetchPartnerSettlement,
  fetchPayoutDetail,
  markPayoutPaid,
  rejectPayout,
} from "../../api/finance";
import AdminWriteActionModal from "../../components/admin/AdminWriteActionModal";
import BlockersPanel from "../../components/finance/BlockersPanel";
import { Loader } from "../../components/Loader/Loader";
import { useToast } from "../../components/Toast/useToast";
import { Toast } from "../../components/Toast/Toast";
import { extractRequestId } from "../ops/opsUtils";
import { useAdmin } from "../../admin/AdminContext";
import { useAuth } from "../../auth/AuthContext";
import { ApiError } from "../../api/http";
import { CopyButton } from "../../components/CopyButton/CopyButton";
import { JsonViewer } from "../../components/common/JsonViewer";

type ActionType = "approve" | "reject" | "mark-paid" | null;

export const PayoutDetailsPage: React.FC = () => {
  const { payoutId } = useParams();
  const { toast, showToast } = useToast();
  const { accessToken } = useAuth();
  const { profile } = useAdmin();
  const [action, setAction] = useState<ActionType>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [settlementError, setSettlementError] = useState<string | null>(null);
  const canWrite = Boolean(profile?.permissions.finance?.write) && !profile?.read_only;

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["payout-detail", payoutId],
    queryFn: () => fetchPayoutDetail(payoutId || ""),
    enabled: Boolean(payoutId),
  });

  const requestId = useMemo(() => (errorMessage ? extractRequestId(new Error(errorMessage)) : null), [errorMessage]);

  const partnerId = data?.partner_id ?? null;
  const { data: ledgerData } = useQuery({
    queryKey: ["partner-ledger", partnerId],
    queryFn: () => fetchPartnerLedger(partnerId as string),
    enabled: Boolean(partnerId),
  });
  const { data: settlementData } = useQuery({
    queryKey: ["partner-settlement", partnerId],
    queryFn: () => fetchPartnerSettlement(partnerId as string),
    enabled: Boolean(partnerId),
  });

  const handleConfirm = async ({ reason, correlationId }: { reason: string; correlationId: string }) => {
    if (!payoutId || !accessToken) return;
    if (!canWrite) return;
    try {
      setSettlementError(null);
      if (action === "approve") {
        await approvePayout(accessToken, payoutId, { reason, correlation_id: correlationId });
      } else if (action === "reject") {
        await rejectPayout(accessToken, payoutId, { reason, correlation_id: correlationId });
      } else if (action === "mark-paid") {
        await markPayoutPaid(accessToken, payoutId, { reason, correlation_id: correlationId });
      }
      setAction(null);
      setErrorMessage(null);
      showToast("success", "Action completed");
      await refetch();
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      if (error instanceof ApiError && error.status === 409) {
        setSettlementError(error.errorCode ?? "missing_settlement");
      }
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
        <div>Partner ID: {data.partner_id ?? "—"}</div>
        <div>
          Amount: {data.amount} {data.currency}
        </div>
        <div>Created: {data.created_at ?? "—"}</div>
        <div>Processed: {data.processed_at ?? "—"}</div>
        <div>Legal status: {data.legal_status ?? "—"}</div>
        <div>Settlement status: {data.settlement_status ?? "—"}</div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span>Correlation ID: {data.correlation_id ?? "—"}</span>
          {data.correlation_id ? <CopyButton value={data.correlation_id} /> : null}
        </div>
      </div>

      <BlockersPanel blockers={data.blockers} title="Blockers" />

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Block reason tree</h3>
        {data.block_reason_tree ? (
          <JsonViewer value={data.block_reason_tree} redactionMode="audit" />
        ) : (
          <div className="muted">No block tree data.</div>
        )}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Policy</h3>
        <div>Min payout: {data.policy?.min_payout_amount ?? "—"}</div>
        <div>Hold days: {data.policy?.payout_hold_days ?? "—"}</div>
        <div>Schedule: {data.policy?.payout_schedule ?? "—"}</div>
      </div>

      <div
        className="card"
        style={{
          border: settlementError ? "1px solid #dc2626" : undefined,
          background: settlementError ? "rgba(220, 38, 38, 0.05)" : undefined,
        }}
      >
        <h3 style={{ marginTop: 0 }}>Settlement snapshot</h3>
        {settlementError ? (
          <div style={{ color: "#dc2626", marginBottom: 8 }}>
            Settlement snapshot missing (reason: {settlementError})
          </div>
        ) : null}
        {data.settlement_snapshot || settlementData ? (
          <JsonViewer value={data.settlement_snapshot ?? settlementData ?? {}} redactionMode="audit" />
        ) : (
          <div className="muted">Нет settlement snapshot</div>
        )}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Partner ledger</h3>
        {ledgerData ? (
          <JsonViewer value={ledgerData} redactionMode="audit" />
        ) : (
          <div className="muted">Нет данных ledger</div>
        )}
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

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Correlation chain</h3>
        {data.correlation_chain?.length ? (
          <ul style={{ paddingLeft: 18, marginBottom: 0 }}>
            {data.correlation_chain.map((item) => (
              <li key={item} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span>{item}</span>
                <CopyButton value={item} />
              </li>
            ))}
          </ul>
        ) : data.correlation_id ? (
          <div className="muted">
            Single correlation ID available. <CopyButton value={data.correlation_id} label="Copy" />
          </div>
        ) : (
          <div className="muted">No correlation chain.</div>
        )}
      </div>

      <div className="card" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button type="button" className="neft-btn" onClick={() => setAction("approve")} disabled={!canWrite}>
          Approve
        </button>
        <button type="button" className="neft-btn-secondary" onClick={() => setAction("mark-paid")} disabled={!canWrite}>
          Mark paid
        </button>
        <button type="button" className="ghost" onClick={() => setAction("reject")} disabled={!canWrite}>
          Reject
        </button>
        {!canWrite ? <span className="muted">Read-only mode enabled</span> : null}
      </div>

      <AdminWriteActionModal
        isOpen={action !== null}
        title="Confirm payout action"
        requirePhrase
        confirmPhrase="CONFIRM"
        onConfirm={handleConfirm}
        onCancel={() => setAction(null)}
      />

      <Toast toast={toast} />
    </div>
  );
};

export default PayoutDetailsPage;
