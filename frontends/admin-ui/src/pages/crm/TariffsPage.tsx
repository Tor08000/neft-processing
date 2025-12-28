import React, { useEffect, useMemo, useState } from "react";
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

export const TariffsPage: React.FC = () => {
  const navigate = useNavigate();
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [tariffs, setTariffs] = useState<CrmTariff[]>([]);
  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [saving, setSaving] = useState(false);
  const [canCreate, setCanCreate] = useState(true);

  const columns: DataColumn<CrmTariff>[] = useMemo(
    () => [
      { key: "tariff_id", title: "Tariff ID", render: (row) => row.tariff_id ?? row.id ?? "-" },
      { key: "name", title: "Name" },
      { key: "status", title: "Status", render: (row) => (row.status ? <StatusBadge status={row.status} /> : "-") },
      { key: "base_fee", title: "Base fee" },
      {
        key: "domains",
        title: "Domains",
        render: (row) =>
          row.domains
            ? Object.entries(row.domains)
                .filter(([, enabled]) => enabled)
                .map(([key]) => key)
                .join(", ") || "-"
            : "-",
      },
      { key: "included_summary", title: "Included" },
    ],
    [],
  );

  const loadTariffs = () => {
    if (!accessToken) return;
    setLoading(true);
    listTariffs(accessToken)
      .then((response) => setTariffs(response.items))
      .catch((error: unknown) => showToast("error", formatError(error)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadTariffs();
  }, [accessToken]);

  const handleCreate = async (values: Partial<CrmTariff>) => {
    if (!accessToken) return;
    setSaving(true);
    try {
      await createTariff(accessToken, values);
      showToast("success", "Tariff created");
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
      <h1>CRM · Tariffs</h1>
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        {canCreate && (
          <button type="button" onClick={() => setShowCreate((prev) => !prev)}>
            {showCreate ? "Close" : "Create tariff"}
          </button>
        )}
      </div>
      {showCreate && (
        <div style={{ marginBottom: 24, border: "1px solid #e2e8f0", padding: 16, borderRadius: 12 }}>
          <TariffForm onSubmit={handleCreate} submitting={saving} submitLabel="Create" />
        </div>
      )}
      <DataTable
        data={tariffs}
        columns={columns}
        loading={loading}
        onRowClick={(row) => navigate(`/crm/tariffs/${row.tariff_id ?? row.id}`)}
      />
    </div>
  );
};

export default TariffsPage;
