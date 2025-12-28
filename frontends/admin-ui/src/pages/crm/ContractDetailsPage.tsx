import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  activateContract,
  applyContract,
  getContract,
  listLimitProfiles,
  listRiskProfiles,
  pauseContract,
  terminateContract,
  updateContract,
} from "../../api/crm";
import { useAuth } from "../../auth/AuthContext";
import { ContractForm } from "../../components/crm/ContractForm";
import { ConfirmModal } from "../../components/common/ConfirmModal";
import { JsonViewer } from "../../components/common/JsonViewer";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import type { CrmContract, CrmProfile } from "../../types/crm";
import { describeError, formatError } from "../../utils/apiErrors";

const actionLabels = {
  activate: "Activate",
  pause: "Pause",
  terminate: "Terminate",
  apply: "Apply",
};

export const ContractDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [contract, setContract] = useState<CrmContract | null>(null);
  const [loading, setLoading] = useState(true);
  const [applyResult, setApplyResult] = useState<Record<string, unknown> | null>(null);
  const [confirmAction, setConfirmAction] = useState<null | keyof typeof actionLabels>(null);
  const [saving, setSaving] = useState(false);
  const [limitProfiles, setLimitProfiles] = useState<CrmProfile[]>([]);
  const [riskProfiles, setRiskProfiles] = useState<CrmProfile[]>([]);
  const [actionVisibility, setActionVisibility] = useState<Record<keyof typeof actionLabels, boolean>>({
    activate: true,
    pause: true,
    terminate: true,
    apply: true,
  });

  const loadContract = () => {
    if (!accessToken || !id) return;
    setLoading(true);
    Promise.all([getContract(accessToken, id), listLimitProfiles(accessToken), listRiskProfiles(accessToken)])
      .then(([response, limitResponse, riskResponse]) => {
        setContract(response);
        setLimitProfiles(limitResponse.items ?? []);
        setRiskProfiles(riskResponse.items ?? []);
      })
      .catch((error: unknown) => showToast("error", formatError(error)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadContract();
  }, [accessToken, id]);

  const handleAction = async (action: keyof typeof actionLabels) => {
    if (!accessToken || !contract) return;
    const contractId = contract.contract_id ?? contract.id ?? "";
    try {
      if (action === "activate") {
        await activateContract(accessToken, contractId);
      }
      if (action === "pause") {
        await pauseContract(accessToken, contractId);
      }
      if (action === "terminate") {
        await terminateContract(accessToken, contractId);
      }
      if (action === "apply") {
        const result = await applyContract(accessToken, contractId);
        setApplyResult(result);
      }
      showToast("success", `${actionLabels[action]} done`);
      loadContract();
    } catch (error: unknown) {
      const summary = describeError(error);
      if (summary.isForbidden) {
        setActionVisibility((prev) => ({ ...prev, [action]: false }));
      }
      showToast("error", formatError(error));
    } finally {
      setConfirmAction(null);
    }
  };

  const handleUpdate = async (values: Partial<CrmContract>) => {
    if (!accessToken || !contract) return;
    const contractId = contract.contract_id ?? contract.id ?? "";
    setSaving(true);
    try {
      const updated = await updateContract(accessToken, contractId, values);
      setContract(updated);
      showToast("success", "Contract updated");
    } catch (error: unknown) {
      showToast("error", formatError(error));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div>Loading...</div>;
  }

  if (!contract) {
    return <div>Contract not found</div>;
  }

  return (
    <div>
      <Toast toast={toast} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>Contract {contract.contract_number ?? contract.contract_id ?? contract.id}</h1>
        <button type="button" onClick={() => navigate(`/crm/clients/${contract.client_id}`)}>
          Client details
        </button>
      </div>
      <div style={{ display: "grid", gap: 8, marginBottom: 16 }}>
        <div>Status: {contract.status ? <StatusBadge status={contract.status} /> : "-"}</div>
        <div>Valid: {contract.valid_from ?? "-"} → {contract.valid_to ?? "-"}</div>
        <div>Tariff: {contract.tariff_plan_id ?? "-"}</div>
        <div>Risk profile: {contract.risk_profile_id ?? "-"}</div>
        <div>Limit profile: {contract.limit_profile_id ?? "-"}</div>
        <div>Documents required: {contract.documents_required ? "Yes" : "No"}</div>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
        {actionVisibility.activate && (
          <button type="button" onClick={() => setConfirmAction("activate")}>Activate</button>
        )}
        {actionVisibility.pause && (
          <button type="button" onClick={() => setConfirmAction("pause")}>Pause</button>
        )}
        {actionVisibility.terminate && (
          <button type="button" onClick={() => setConfirmAction("terminate")}>Terminate</button>
        )}
        {actionVisibility.apply && (
          <button type="button" onClick={() => setConfirmAction("apply")}>Apply</button>
        )}
      </div>

      {contract.audit && (
        <div style={{ marginBottom: 16 }}>
          <h3>Audit snippet</h3>
          <JsonViewer value={contract.audit} />
        </div>
      )}

      {applyResult && (
        <div style={{ marginBottom: 16 }}>
          <h3>Apply result</h3>
          <JsonViewer value={applyResult} />
        </div>
      )}

      <div style={{ marginBottom: 16, border: "1px solid #e2e8f0", padding: 16, borderRadius: 12 }}>
        <h3>Edit contract</h3>
        <ContractForm
          initialValues={contract}
          onSubmit={handleUpdate}
          submitting={saving}
          submitLabel="Update"
          showClientId={false}
          limitProfiles={limitProfiles}
          riskProfiles={riskProfiles}
        />
      </div>

      <div>
        <h3>All fields</h3>
        <JsonViewer value={contract} />
      </div>

      <ConfirmModal
        open={Boolean(confirmAction)}
        title={confirmAction ? `${actionLabels[confirmAction]} contract` : ""}
        description={confirmAction ? `Contract ${contract.contract_number ?? contract.contract_id ?? ""}` : ""}
        danger={confirmAction === "terminate"}
        onCancel={() => setConfirmAction(null)}
        onConfirm={() => {
          if (confirmAction) {
            void handleAction(confirmAction);
          }
        }}
      />
    </div>
  );
};

export default ContractDetailsPage;
