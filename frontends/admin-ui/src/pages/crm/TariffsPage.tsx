import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createTariff, listTariffs } from "../../api/crm";
import { useAuth } from "../../auth/AuthContext";
import { TariffForm } from "../../components/crm/TariffForm";
import { DataTable, type DataColumn } from "../../components/common/DataTable";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import type { CrmTariff } from "../../types/crm";
import { describeError, formatError } from "../../utils/apiErrors";
import { tariffsPageCopy } from "./crmListPageCopy";

export const TariffsPage: React.FC = () => {
  const navigate = useNavigate();
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [tariffs, setTariffs] = useState<CrmTariff[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ title: string; description?: string; details?: string } | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [saving, setSaving] = useState(false);
  const [canCreate, setCanCreate] = useState(true);

  const columns: DataColumn<CrmTariff>[] = useMemo(
    () => [
      { key: "tariff_id", title: tariffsPageCopy.columns.tariffId, render: (row) => row.tariff_id ?? row.id ?? tariffsPageCopy.values.fallback },
      { key: "name", title: tariffsPageCopy.columns.name },
      {
        key: "status",
        title: tariffsPageCopy.columns.status,
        render: (row) => (row.status ? <StatusBadge status={row.status} /> : tariffsPageCopy.values.fallback),
      },
      { key: "billing_period", title: tariffsPageCopy.columns.billingPeriod },
      { key: "base_fee_minor", title: tariffsPageCopy.columns.baseFeeMinor },
      {
        key: "features",
        title: tariffsPageCopy.columns.features,
        render: (row) =>
          row.features
            ? Object.entries(row.features)
                .filter(([, enabled]) => enabled)
                .map(([key]) => key)
                .join(", ") || tariffsPageCopy.values.fallback
            : tariffsPageCopy.values.fallback,
      },
      { key: "currency", title: tariffsPageCopy.columns.currency },
    ],
    [],
  );

  const loadTariffs = useCallback(() => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    listTariffs(accessToken)
      .then((response) => setTariffs(response.items))
      .catch((error: unknown) => {
        const summary = describeError(error);
        setError({ title: tariffsPageCopy.errors.load, description: summary.message, details: summary.details });
        showToast("error", formatError(error));
      })
      .finally(() => setLoading(false));
  }, [accessToken, showToast]);

  useEffect(() => {
    loadTariffs();
  }, [accessToken, loadTariffs]);

  const handleCreate = async (values: Partial<CrmTariff>) => {
    if (!accessToken) return;
    setSaving(true);
    try {
      await createTariff(accessToken, values);
      showToast("success", tariffsPageCopy.toasts.created);
      setShowCreate(false);
      loadTariffs();
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

  return (
    <div>
      <Toast toast={toast} />
      <h1>{tariffsPageCopy.title}</h1>
      {showCreate && (
        <div style={{ marginBottom: 24, border: "1px solid #e2e8f0", padding: 16, borderRadius: 12 }}>
          <TariffForm onSubmit={handleCreate} submitting={saving} submitLabel="Create" />
        </div>
      )}
      <DataTable
        data={tariffs}
        columns={columns}
        loading={loading}
        toolbar={
          <div className="table-toolbar">
            <div className="toolbar-actions">
              {canCreate ? (
                <button type="button" className="button primary" onClick={() => setShowCreate((prev) => !prev)}>
                  {showCreate ? tariffsPageCopy.actions.close : tariffsPageCopy.actions.create}
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
                actionLabel: tariffsPageCopy.actions.retry,
                actionOnClick: loadTariffs,
              }
            : undefined
        }
        footer={<div className="table-footer__content muted">{tariffsPageCopy.footer.rows(tariffs.length)}</div>}
        emptyState={{
          title: tariffsPageCopy.empty.title,
          description: tariffsPageCopy.empty.description,
          actionLabel: canCreate ? tariffsPageCopy.actions.create : undefined,
          actionOnClick: canCreate ? () => setShowCreate(true) : undefined,
        }}
        onRowClick={(row) => navigate(`/crm/tariffs/${row.id}`)}
      />
    </div>
  );
};

export default TariffsPage;
