import React, { useCallback, useEffect, useMemo, useState } from "react";
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
import { contractsPageCopy } from "./crmListPageCopy";

export const ContractsPage: React.FC = () => {
  const navigate = useNavigate();
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [contracts, setContracts] = useState<CrmContract[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ title: string; description?: string; details?: string } | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [clientFilter, setClientFilter] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [saving, setSaving] = useState(false);
  const [canCreate, setCanCreate] = useState(true);
  const [limitProfiles, setLimitProfiles] = useState<CrmProfile[]>([]);
  const [riskProfiles, setRiskProfiles] = useState<CrmProfile[]>([]);
  const [confirmAction, setConfirmAction] = useState<null | { action: keyof typeof contractsPageCopy.actionLabels; contract: CrmContract }>(
    null,
  );
  const [actionVisibility, setActionVisibility] = useState<Record<keyof typeof contractsPageCopy.actionLabels, boolean>>({
    activate: true,
    pause: true,
    terminate: true,
    apply: true,
  });
  const filtersActive = Boolean(statusFilter.trim() || clientFilter.trim());

  const loadContracts = useCallback(() => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    listContracts(accessToken, { status: statusFilter || undefined, client_id: clientFilter || undefined })
      .then((response) => setContracts(response.items))
      .catch((error: unknown) => {
        const summary = describeError(error);
        setError({ title: contractsPageCopy.errors.load, description: summary.message, details: summary.details });
        showToast("error", formatError(error));
      })
      .finally(() => setLoading(false));
  }, [accessToken, clientFilter, showToast, statusFilter]);

  useEffect(() => {
    loadContracts();
    if (!accessToken) return;
    Promise.all([listLimitProfiles(accessToken), listRiskProfiles(accessToken)])
      .then(([limitResponse, riskResponse]) => {
        setLimitProfiles(limitResponse.items ?? []);
        setRiskProfiles(riskResponse.items ?? []);
      })
      .catch((error: unknown) => showToast("error", formatError(error)));
  }, [accessToken, clientFilter, loadContracts, showToast, statusFilter]);

  const handleCreate = async (values: Partial<CrmContract>) => {
    if (!accessToken) return;
    const clientId = values.client_id ?? clientFilter;
    if (!clientId) {
      showToast("error", contractsPageCopy.errors.clientIdRequired);
      return;
    }
    setSaving(true);
    try {
      await createContract(accessToken, clientId, values);
      showToast("success", contractsPageCopy.toasts.created);
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

  const handleAction = async (action: keyof typeof contractsPageCopy.actionLabels, contract: CrmContract) => {
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
      showToast("success", contractsPageCopy.toasts.done(contractsPageCopy.actionLabels[action]));
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
      { key: "contract_number", title: contractsPageCopy.columns.contract },
      { key: "client_id", title: contractsPageCopy.columns.client },
      { key: "status", title: contractsPageCopy.columns.status, render: (row) => (row.status ? <StatusBadge status={row.status} /> : contractsPageCopy.values.fallback) },
      {
        key: "valid",
        title: contractsPageCopy.columns.valid,
        render: (row) => `${row.valid_from ?? contractsPageCopy.values.fallback} → ${row.valid_to ?? contractsPageCopy.values.fallback}`,
      },
      { key: "billing_mode", title: contractsPageCopy.columns.billingMode },
      { key: "currency", title: contractsPageCopy.columns.currency },
      { key: "risk_profile_id", title: contractsPageCopy.columns.riskProfile },
      { key: "limit_profile_id", title: contractsPageCopy.columns.limitProfile },
      {
        key: "documents_required",
        title: contractsPageCopy.columns.docsRequired,
        render: (row) => (row.documents_required ? contractsPageCopy.values.yes : contractsPageCopy.values.no),
      },
      {
        key: "actions",
        title: contractsPageCopy.columns.actions,
        render: (row) => (
          <div className="table-row-actions">
            {actionVisibility.activate ? (
              <button
                type="button"
                className="ghost"
                onClick={(event) => {
                  event.stopPropagation();
                  setConfirmAction({ action: "activate", contract: row });
                }}
              >
                {contractsPageCopy.actionLabels.activate}
              </button>
            ) : null}
            {actionVisibility.pause ? (
              <button
                type="button"
                className="ghost"
                onClick={(event) => {
                  event.stopPropagation();
                  setConfirmAction({ action: "pause", contract: row });
                }}
              >
                {contractsPageCopy.actionLabels.pause}
              </button>
            ) : null}
            {actionVisibility.terminate ? (
              <button
                type="button"
                className="ghost"
                onClick={(event) => {
                  event.stopPropagation();
                  setConfirmAction({ action: "terminate", contract: row });
                }}
              >
                {contractsPageCopy.actionLabels.terminate}
              </button>
            ) : null}
            {actionVisibility.apply ? (
              <button
                type="button"
                className="ghost"
                onClick={(event) => {
                  event.stopPropagation();
                  setConfirmAction({ action: "apply", contract: row });
                }}
              >
                {contractsPageCopy.actionLabels.apply}
              </button>
            ) : null}
          </div>
        ),
      },
    ],
    [actionVisibility],
  );

  return (
    <div>
      <Toast toast={toast} />
      <h1>{contractsPageCopy.title}</h1>
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
        toolbar={
          <div className="table-toolbar">
            <div className="filters">
              <div className="filter">
                <label className="label" htmlFor="crm-contract-client-filter">
                  {contractsPageCopy.labels.clientId}
                </label>
                <input
                  id="crm-contract-client-filter"
                  placeholder={contractsPageCopy.placeholders.clientId}
                  value={clientFilter}
                  onChange={(e) => setClientFilter(e.target.value)}
                />
              </div>
              <div className="filter">
                <label className="label" htmlFor="crm-contract-status-filter">
                  {contractsPageCopy.labels.status}
                </label>
                <input
                  id="crm-contract-status-filter"
                  placeholder={contractsPageCopy.placeholders.status}
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                />
              </div>
            </div>
            <div className="toolbar-actions">
              <button
                type="button"
                className="button secondary"
                onClick={() => {
                  setClientFilter("");
                  setStatusFilter("");
                }}
                disabled={!filtersActive}
              >
                {contractsPageCopy.actions.reset}
              </button>
              {canCreate ? (
                <button type="button" className="button primary" onClick={() => setShowCreate((prev) => !prev)}>
                  {showCreate ? contractsPageCopy.actions.close : contractsPageCopy.actions.create}
                </button>
              ) : null}
            </div>
          </div>
        }
        errorState={
          error
            ? {
                title: error.title,
                description: error.description,
                details: error.details,
                actionLabel: contractsPageCopy.actions.retry,
                actionOnClick: loadContracts,
              }
            : undefined
        }
        footer={<div className="table-footer__content muted">{contractsPageCopy.footer.rows(contracts.length)}</div>}
        emptyState={{
          title: filtersActive ? contractsPageCopy.empty.filteredTitle : contractsPageCopy.empty.pristineTitle,
          description: filtersActive
            ? contractsPageCopy.empty.filteredDescription
            : contractsPageCopy.empty.pristineDescription,
          actionLabel: filtersActive ? contractsPageCopy.empty.resetAction : canCreate ? contractsPageCopy.actions.create : undefined,
          actionOnClick: filtersActive
            ? () => {
                setClientFilter("");
                setStatusFilter("");
              }
            : canCreate
              ? () => setShowCreate(true)
              : undefined,
        }}
        onRowClick={(row) => navigate(`/crm/contracts/${row.id}`)}
      />

      <ConfirmModal
        open={Boolean(confirmAction)}
        title={confirmAction ? contractsPageCopy.confirm.title(contractsPageCopy.actionLabels[confirmAction.action]) : ""}
        description={
          confirmAction
            ? contractsPageCopy.confirm.description(
                confirmAction.contract.contract_number ?? confirmAction.contract.contract_id ?? "",
              )
            : ""
        }
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
