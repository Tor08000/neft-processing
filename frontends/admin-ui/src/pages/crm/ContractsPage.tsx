import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  activateContract,
  applyContract,
  createContract,
  listContracts,
  listLimitProfiles,
  listRiskProfiles,
  pauseContract,
  terminateContract,
} from "../../api/crm";
import { useAuth } from "../../auth/AuthContext";
import { ContractForm } from "../../components/crm/ContractForm";
import { ConfirmModal } from "../../components/common/ConfirmModal";
import { DataTable, type DataColumn } from "../../components/common/DataTable";
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

export const ContractsPage: React.FC = () => {
  const navigate = useNavigate();
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [contracts, setContracts] = useState<CrmContract[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");
  const [clientFilter, setClientFilter] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [saving, setSaving] = useState(false);
  const [canCreate, setCanCreate] = useState(true);
  const [limitProfiles, setLimitProfiles] = useState<CrmProfile[]>([]);
  const [riskProfiles, setRiskProfiles] = useState<CrmProfile[]>([]);
  const [confirmAction, setConfirmAction] = useState<null | { action: keyof typeof actionLabels; contract: CrmContract }>(
    null,
  );
  const [actionVisibility, setActionVisibility] = useState<Record<keyof typeof actionLabels, boolean>>({
    activate: true,
    pause: true,
    terminate: true,
    apply: true,
  });

  const loadContracts = () => {
    if (!accessToken) return;
    setLoading(true);
    listContracts(accessToken, { status: statusFilter || undefined, client_id: clientFilter || undefined })
      .then((response) => setContracts(response.items))
      .catch((error: unknown) => showToast("error", formatError(error)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadContracts();
    if (!accessToken) return;
    Promise.all([listLimitProfiles(accessToken), listRiskProfiles(accessToken)])
      .then(([limitResponse, riskResponse]) => {
        setLimitProfiles(limitResponse.items ?? []);
        setRiskProfiles(riskResponse.items ?? []);
      })
      .catch((error: unknown) => showToast("error", formatError(error)));
  }, [accessToken, statusFilter, clientFilter]);

  const handleCreate = async (values: Partial<CrmContract>) => {
    if (!accessToken) return;
    const clientId = values.client_id ?? clientFilter;
    if (!clientId) {
      showToast("error", "Client ID is required");
      return;
    }
    setSaving(true);
    try {
      await createContract(accessToken, clientId, values);
      showToast("success", "Contract created");
      setShowCreate(false);
      loadContracts();
    } catch (error: unknown) {
      const summary = describeError(error);
      if (summary.isForbidden) {
        setCanCreate(false);
      }
      showToast("error", formatError(error));
    } finally {
      setSaving(false);
    }
  };

  const handleAction = async (action: keyof typeof actionLabels, contract: CrmContract) => {
    if (!accessToken) return;
    try {
      if (action === "activate") {
        await activateContract(accessToken, contract.contract_id ?? contract.id ?? "");
      }
      if (action === "pause") {
        await pauseContract(accessToken, contract.contract_id ?? contract.id ?? "");
      }
      if (action === "terminate") {
        await terminateContract(accessToken, contract.contract_id ?? contract.id ?? "");
      }
      if (action === "apply") {
        await applyContract(accessToken, contract.contract_id ?? contract.id ?? "");
      }
      showToast("success", `${actionLabels[action]} done`);
      loadContracts();
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

  const columns: DataColumn<CrmContract>[] = useMemo(
    () => [
      { key: "contract_number", title: "Contract" },
      { key: "client_id", title: "Client" },
      { key: "status", title: "Status", render: (row) => (row.status ? <StatusBadge status={row.status} /> : "-") },
      {
        key: "valid",
        title: "Valid",
        render: (row) => `${row.valid_from ?? "-"} → ${row.valid_to ?? "-"}`,
      },
      { key: "tariff_plan_id", title: "Tariff" },
      { key: "risk_profile_id", title: "Risk profile" },
      { key: "limit_profile_id", title: "Limit profile" },
      {
        key: "documents_required",
        title: "Docs required",
        render: (row) => (row.documents_required ? "Yes" : "No"),
      },
    ],
    [],
  );

  return (
    <div>
      <Toast toast={toast} />
      <h1>CRM · Contracts</h1>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
        <input placeholder="Client ID" value={clientFilter} onChange={(e) => setClientFilter(e.target.value)} />
        <input placeholder="Status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} />
        {canCreate && (
          <button type="button" onClick={() => setShowCreate((prev) => !prev)}>
            {showCreate ? "Close" : "Create contract"}
          </button>
        )}
      </div>
      {showCreate && (
        <div style={{ marginBottom: 24, border: "1px solid #e2e8f0", padding: 16, borderRadius: 12 }}>
          <ContractForm
            onSubmit={handleCreate}
            submitting={saving}
            submitLabel="Create"
            limitProfiles={limitProfiles}
            riskProfiles={riskProfiles}
          />
        </div>
      )}

      <DataTable
        data={contracts}
        columns={columns}
        loading={loading}
        onRowClick={(row) => navigate(`/crm/contracts/${row.contract_id ?? row.id}`)}
      />

      <div style={{ marginTop: 16, display: "grid", gap: 8 }}>
        {contracts.map((contract) => (
          <div key={contract.contract_id ?? contract.id} style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <strong>{contract.contract_number ?? contract.contract_id ?? contract.id}</strong>
            {actionVisibility.activate && (
              <button type="button" onClick={() => setConfirmAction({ action: "activate", contract })}>
                Activate
              </button>
            )}
            {actionVisibility.pause && (
              <button type="button" onClick={() => setConfirmAction({ action: "pause", contract })}>
                Pause
              </button>
            )}
            {actionVisibility.terminate && (
              <button type="button" onClick={() => setConfirmAction({ action: "terminate", contract })}>
                Terminate
              </button>
            )}
            {actionVisibility.apply && (
              <button type="button" onClick={() => setConfirmAction({ action: "apply", contract })}>
                Apply
              </button>
            )}
          </div>
        ))}
      </div>

      <ConfirmModal
        open={Boolean(confirmAction)}
        title={confirmAction ? `${actionLabels[confirmAction.action]} contract` : ""}
        description={confirmAction ? `Contract ${confirmAction.contract.contract_number ?? confirmAction.contract.contract_id ?? ""}` : ""}
        danger={confirmAction?.action === "terminate"}
        onCancel={() => setConfirmAction(null)}
        onConfirm={() => {
          if (confirmAction) {
            void handleAction(confirmAction.action, confirmAction.contract);
          }
        }}
      />
    </div>
  );
};

export default ContractsPage;
