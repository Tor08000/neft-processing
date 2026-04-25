import React, { useCallback, useEffect, useMemo, useState } from "react";
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
import { clientsPageCopy } from "./crmListPageCopy";

export const ClientsPage: React.FC = () => {
  const navigate = useNavigate();
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [clients, setClients] = useState<CrmClient[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ title: string; description?: string; details?: string } | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [saving, setSaving] = useState(false);
  const [canCreate, setCanCreate] = useState(true);
  const filtersActive = Boolean(statusFilter.trim() || search.trim());

  const columns: DataColumn<CrmClient>[] = useMemo(
    () => [
      { key: "client_id", title: clientsPageCopy.columns.clientId },
      { key: "legal_name", title: clientsPageCopy.columns.legalName },
      {
        key: "status",
        title: clientsPageCopy.columns.status,
        render: (row) => (row.status ? <StatusBadge status={row.status} /> : "-"),
      },
      {
        key: "country",
        title: clientsPageCopy.columns.countryTimezone,
        render: (row) => `${row.country ?? "-"} / ${row.timezone ?? "-"}`,
      },
    ],
    [],
  );

  const loadClients = useCallback(() => {
    if (!accessToken) return;
    setLoading(true);
    setError(null);
    listClients(accessToken, { status: statusFilter || undefined, search: search || undefined })
      .then((response) => setClients(response.items))
      .catch((error: unknown) => {
        const summary = describeError(error);
        setError({ title: clientsPageCopy.errors.load, description: summary.message, details: summary.details });
        showToast("error", formatError(error));
      })
      .finally(() => setLoading(false));
  }, [accessToken, search, showToast, statusFilter]);

  useEffect(() => {
    loadClients();
  }, [loadClients]);

  const handleCreate = async (values: Partial<CrmClient>) => {
    if (!accessToken) return;
    setSaving(true);
    try {
      await createClient(accessToken, values);
      showToast("success", clientsPageCopy.toasts.created);
      setShowCreate(false);
      loadClients();
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
      <h1>{clientsPageCopy.title}</h1>
      {showCreate && (
        <div style={{ marginBottom: 24, border: "1px solid #e2e8f0", padding: 16, borderRadius: 12 }}>
          <ClientForm onSubmit={handleCreate} submitting={saving} submitLabel="Create" />
        </div>
      )}
      <DataTable
        data={clients}
        columns={columns}
        loading={loading}
        toolbar={
          <div className="table-toolbar">
            <div className="filters">
              <div className="filter filter--wide">
                <label className="label" htmlFor="crm-client-search">
                  {clientsPageCopy.labels.search}
                </label>
                <input
                  id="crm-client-search"
                  placeholder={clientsPageCopy.placeholders.search}
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              <div className="filter">
                <label className="label" htmlFor="crm-client-status">
                  {clientsPageCopy.labels.status}
                </label>
                <input
                  id="crm-client-status"
                  placeholder={clientsPageCopy.placeholders.status}
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
                  setSearch("");
                  setStatusFilter("");
                }}
                disabled={!filtersActive}
              >
                {clientsPageCopy.actions.reset}
              </button>
              {canCreate ? (
                <button type="button" className="button primary" onClick={() => setShowCreate((prev) => !prev)}>
                  {showCreate ? clientsPageCopy.actions.close : clientsPageCopy.actions.create}
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
                actionLabel: clientsPageCopy.actions.retry,
                actionOnClick: loadClients,
              }
            : undefined
        }
        footer={<div className="table-footer__content muted">{clientsPageCopy.footer.rows(clients.length)}</div>}
        emptyState={{
          title: filtersActive ? clientsPageCopy.empty.filteredTitle : clientsPageCopy.empty.pristineTitle,
          description: filtersActive
            ? clientsPageCopy.empty.filteredDescription
            : clientsPageCopy.empty.pristineDescription,
          actionLabel: filtersActive ? clientsPageCopy.empty.resetAction : canCreate ? clientsPageCopy.actions.create : undefined,
          actionOnClick: filtersActive
            ? () => {
                setSearch("");
                setStatusFilter("");
              }
            : canCreate
              ? () => setShowCreate(true)
              : undefined,
        }}
        onRowClick={(row) => navigate(`/crm/clients/${row.id}`)}
      />
    </div>
  );
};

export default ClientsPage;
