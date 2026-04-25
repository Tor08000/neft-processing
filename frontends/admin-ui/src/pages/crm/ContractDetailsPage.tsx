import React, { useCallback, useEffect, useState } from "react";
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
import { ConfirmModal } from "../../components/common/ConfirmModal";
import { EmptyState } from "../../components/common/EmptyState";
import { ErrorState } from "../../components/common/ErrorState";
import { JsonViewer } from "../../components/common/JsonViewer";
import { Loader } from "../../components/Loader/Loader";
import { Toast } from "../../components/common/Toast";
import { ContractForm } from "../../components/crm/ContractForm";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import { useToast } from "../../components/Toast/useToast";
import type { CrmContract, CrmProfile } from "../../types/crm";
import { describeError, formatError } from "../../utils/apiErrors";

const actionLabels = {
  activate: "Activate",
  pause: "Pause",
  terminate: "Terminate",
  apply: "Apply",
};

const EMPTY_VALUE = "-";

export const ContractDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [contract, setContract] = useState<CrmContract | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadErrorDetails, setLoadErrorDetails] = useState<string | undefined>(undefined);
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

  const loadContract = useCallback(() => {
    if (!accessToken || !id) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setLoadError(null);
    setLoadErrorDetails(undefined);
    setContract(null);
    setLimitProfiles([]);
    setRiskProfiles([]);
    Promise.all([getContract(accessToken, id), listLimitProfiles(accessToken), listRiskProfiles(accessToken)])
      .then(([response, limitResponse, riskResponse]) => {
        setContract(response);
        setLimitProfiles(limitResponse.items ?? []);
        setRiskProfiles(riskResponse.items ?? []);
      })
      .catch((error: unknown) => {
        const summary = describeError(error);
        setLoadError(summary.message);
        setLoadErrorDetails(summary.details);
        showToast("error", formatError(error));
      })
      .finally(() => setLoading(false));
  }, [accessToken, id, showToast]);

  useEffect(() => {
    loadContract();
  }, [loadContract]);

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
    return <Loader label="Loading contract detail" />;
  }

  if (!id) {
    return (
      <EmptyState
        title="Contract ID is required"
        description="Open the contract detail page from the CRM contracts list."
        primaryAction={{ label: "Back to contracts", onClick: () => navigate("/crm/contracts") }}
      />
    );
  }

  if (loadError) {
    return (
      <ErrorState
        title="Failed to load contract detail"
        description={loadError}
        details={loadErrorDetails}
        actionLabel="Retry"
        onAction={() => void loadContract()}
      />
    );
  }

  if (!contract) {
    return (
      <EmptyState
        title="Contract not found"
        description="The requested contract is missing or no longer available."
        primaryAction={{ label: "Back to contracts", onClick: () => navigate("/crm/contracts") }}
      />
    );
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
        <div>Status: {contract.status ? <StatusBadge status={contract.status} /> : EMPTY_VALUE}</div>
        <div>
          Valid: {contract.valid_from ?? EMPTY_VALUE} {"->"} {contract.valid_to ?? EMPTY_VALUE}
        </div>
        <div>Billing mode: {contract.billing_mode ?? EMPTY_VALUE}</div>
        <div>Currency: {contract.currency ?? EMPTY_VALUE}</div>
        <div>Risk profile: {contract.risk_profile_id ?? EMPTY_VALUE}</div>
        <div>Limit profile: {contract.limit_profile_id ?? EMPTY_VALUE}</div>
        <div>Documents required: {contract.documents_required ? "Yes" : "No"}</div>
        <div>CRM contract version: {contract.crm_contract_version ?? EMPTY_VALUE}</div>
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
        {actionVisibility.activate && (
          <button type="button" onClick={() => setConfirmAction("activate")}>
            Activate
          </button>
        )}
        {actionVisibility.pause && (
          <button type="button" onClick={() => setConfirmAction("pause")}>
            Pause
          </button>
        )}
        {actionVisibility.terminate && (
          <button type="button" onClick={() => setConfirmAction("terminate")}>
            Terminate
          </button>
        )}
        {actionVisibility.apply && (
          <button type="button" onClick={() => setConfirmAction("apply")}>
            Apply
          </button>
        )}
      </div>

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
