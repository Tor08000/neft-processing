import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createClient, listClients } from "../../api/crm";
import { useAuth } from "../../auth/AuthContext";
import { ClientForm } from "../../components/crm/ClientForm";
import { DataTable, type DataColumn } from "../../components/common/DataTable";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import type { CrmClient } from "../../types/crm";
import { describeError, formatError } from "../../utils/apiErrors";

export const ClientsPage: React.FC = () => {
  const navigate = useNavigate();
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [clients, setClients] = useState<CrmClient[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [saving, setSaving] = useState(false);
  const [canCreate, setCanCreate] = useState(true);

  const columns: DataColumn<CrmClient>[] = useMemo(
    () => [
      { key: "client_id", title: "Client ID" },
      { key: "legal_name", title: "Legal name" },
      {
        key: "status",
        title: "Status",
        render: (row) => (row.status ? <StatusBadge status={row.status} /> : "-")
      },
      {
        key: "country",
        title: "Country/Timezone",
        render: (row) => `${row.country ?? "-"} / ${row.timezone ?? "-"}`,
      },
      {
        key: "active_contract",
        title: "Active contract",
        render: (row) => (row.active_contract_id ? "Yes" : "No"),
      },
      {
        key: "active_subscription",
        title: "Active subscription",
        render: (row) => (row.active_subscription_id ? "Yes" : "No"),
      },
    ],
    [],
  );

  useEffect(() => {
    if (!accessToken) return;
    setLoading(true);
    listClients(accessToken, { status: statusFilter || undefined, search: search || undefined })
      .then((response) => setClients(response.items))
      .catch((error: unknown) => showToast("error", formatError(error)))
      .finally(() => setLoading(false));
  }, [accessToken, statusFilter, search, showToast]);

  const handleCreate = async (values: Partial<CrmClient>) => {
    if (!accessToken) return;
    setSaving(true);
    try {
      await createClient(accessToken, values);
      showToast("success", "Client created");
      setShowCreate(false);
      const response = await listClients(accessToken, { status: statusFilter || undefined, search: search || undefined });
      setClients(response.items);
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
      <h1>CRM · Clients</h1>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
        <input placeholder="Search by name/id" value={search} onChange={(e) => setSearch(e.target.value)} />
        <input placeholder="Status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} />
        {canCreate && (
          <button type="button" onClick={() => setShowCreate((prev) => !prev)}>
            {showCreate ? "Close" : "Create client"}
          </button>
        )}
      </div>
      {showCreate && (
        <div style={{ marginBottom: 24, border: "1px solid #e2e8f0", padding: 16, borderRadius: 12 }}>
          <ClientForm onSubmit={handleCreate} submitting={saving} submitLabel="Create" />
        </div>
      )}
      <DataTable
        data={clients}
        columns={columns}
        loading={loading}
        onRowClick={(row) => navigate(`/crm/clients/${row.client_id}`)}
      />
    </div>
  );
};

export default ClientsPage;
