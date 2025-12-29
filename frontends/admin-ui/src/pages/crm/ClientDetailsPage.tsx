import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  getClient,
  getClientFeatures,
  listContracts,
  listLimitProfiles,
  listRiskProfiles,
  listSubscriptions,
  updateClient,
  enableFeature,
  disableFeature,
} from "../../api/crm";
import { useAuth } from "../../auth/AuthContext";
import { ClientForm } from "../../components/crm/ClientForm";
import { FeatureFlagsPanel } from "../../components/crm/FeatureFlagsPanel";
import { DataTable, type DataColumn } from "../../components/common/DataTable";
import { JsonViewer } from "../../components/common/JsonViewer";
import { Tabs } from "../../components/common/Tabs";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import type { CrmClient, CrmContract, CrmProfile, CrmSubscription } from "../../types/crm";
import { describeError, formatError } from "../../utils/apiErrors";

export const ClientDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [client, setClient] = useState<CrmClient | null>(null);
  const [contracts, setContracts] = useState<CrmContract[]>([]);
  const [subscriptions, setSubscriptions] = useState<CrmSubscription[]>([]);
  const [features, setFeatures] = useState<Record<string, boolean>>({});
  const [limitProfiles, setLimitProfiles] = useState<CrmProfile[]>([]);
  const [riskProfiles, setRiskProfiles] = useState<CrmProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState("overview");
  const [saving, setSaving] = useState(false);
  const [canToggleFeatures, setCanToggleFeatures] = useState(true);

  useEffect(() => {
    if (!accessToken || !id) return;
    setLoading(true);
    Promise.all([
      getClient(accessToken, id),
      listContracts(accessToken, { client_id: id }),
      listSubscriptions(accessToken, { client_id: id }),
      getClientFeatures(accessToken, id),
      listLimitProfiles(accessToken),
      listRiskProfiles(accessToken),
    ])
      .then(([clientResponse, contractResponse, subscriptionResponse, featuresResponse, limitResponse, riskResponse]) => {
        setClient(clientResponse);
        setContracts(contractResponse.items);
        setSubscriptions(subscriptionResponse.items);
        setFeatures(featuresResponse ?? {});
        setLimitProfiles(limitResponse.items ?? []);
        setRiskProfiles(riskResponse.items ?? []);
      })
      .catch((error: unknown) => showToast("error", formatError(error)))
      .finally(() => setLoading(false));
  }, [accessToken, id, showToast]);

  const handleUpdate = async (values: Partial<CrmClient>) => {
    if (!accessToken || !id) return;
    setSaving(true);
    try {
      const updated = await updateClient(accessToken, id, values);
      setClient(updated);
      showToast("success", "Client updated");
    } catch (error: unknown) {
      showToast("error", formatError(error));
    } finally {
      setSaving(false);
    }
  };

  const handleToggleFeature = async (feature: string, enabled: boolean) => {
    if (!accessToken || !id) return;
    try {
      const next = enabled
        ? await enableFeature(accessToken, id, feature)
        : await disableFeature(accessToken, id, feature);
      setFeatures(next ?? {});
      showToast("success", `Feature ${feature} ${enabled ? "enabled" : "disabled"}`);
    } catch (error: unknown) {
      const summary = describeError(error);
      showToast("error", formatError(error));
      if (summary.isForbidden) {
        setCanToggleFeatures(false);
      }
    }
  };

  const contractColumns: DataColumn<CrmContract>[] = useMemo(
    () => [
      { key: "contract_number", title: "Contract" },
      { key: "status", title: "Status", render: (row) => (row.status ? <StatusBadge status={row.status} /> : "-") },
      {
        key: "period",
        title: "Valid",
        render: (row) => `${row.valid_from ?? "-"} → ${row.valid_to ?? "-"}`,
      },
      { key: "tariff_plan_id", title: "Tariff" },
    ],
    [],
  );

  const subscriptionColumns: DataColumn<CrmSubscription>[] = useMemo(
    () => [
      { key: "subscription_id", title: "Subscription" },
      { key: "status", title: "Status", render: (row) => (row.status ? <StatusBadge status={row.status} /> : "-") },
      { key: "tariff_id", title: "Tariff" },
      { key: "billing_day", title: "Billing day" },
    ],
    [],
  );

  const latestSubscription = subscriptions[0];
  const quickCfoExplainLink = latestSubscription?.subscription_id
    ? `/crm/subscriptions/${latestSubscription.subscription_id}/cfo-explain${
        latestSubscription.last_period_id ? `?period_id=${latestSubscription.last_period_id}` : ""
      }`
    : null;
  const fleetReportLinks = client?.client_id
    ? [
        {
          label: "Driver behavior (7d)",
          href: `/api/v1/admin/fleet-intelligence/drivers?client_id=${client.client_id}&window_days=7`,
        },
        {
          label: "Vehicle efficiency (7d)",
          href: `/api/v1/admin/fleet-intelligence/vehicles?client_id=${client.client_id}&window_days=7`,
        },
        {
          label: "Station trust (7d)",
          href: `/api/v1/admin/fleet-intelligence/stations?tenant_id=${client.tenant_id ?? 0}&window_days=7`,
        },
      ]
    : [];

  if (loading) {
    return <div>Loading...</div>;
  }

  if (!client) {
    return <div>Client not found</div>;
  }

  return (
    <div>
      <Toast toast={toast} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>Client {client.client_id}</h1>
        {quickCfoExplainLink && (
          <button type="button" onClick={() => navigate(quickCfoExplainLink)}>
            CFO Explain
          </button>
        )}
      </div>
      <Tabs
        tabs={[
          { id: "overview", label: "Overview" },
          { id: "contracts", label: "Contracts" },
          { id: "subscriptions", label: "Subscriptions" },
          { id: "features", label: "Feature Flags" },
          { id: "profiles", label: "Profiles" },
        ]}
        active={tab}
        onChange={setTab}
      />

      {tab === "overview" && (
        <div style={{ display: "grid", gap: 16 }}>
          <div style={{ display: "grid", gap: 6 }}>
            <div>Status: {client.status ? <StatusBadge status={client.status} /> : "-"}</div>
            <div>Legal name: {client.legal_name ?? "-"}</div>
            <div>Country: {client.country ?? "-"}</div>
            <div>Timezone: {client.timezone ?? "-"}</div>
            <div>Active contract: {client.active_contract_id ?? "-"}</div>
            <div>Active subscription: {client.active_subscription_id ?? "-"}</div>
          </div>
          <div style={{ border: "1px solid #e2e8f0", padding: 16, borderRadius: 12 }}>
            <h3>Fleet intelligence reports</h3>
            {fleetReportLinks.length > 0 ? (
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {fleetReportLinks.map((link) => (
                  <li key={link.href}>
                    <a href={link.href} target="_blank" rel="noreferrer">
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            ) : (
              <div>No reports available</div>
            )}
          </div>
          <div style={{ border: "1px solid #e2e8f0", padding: 16, borderRadius: 12 }}>
            <h3>Edit client</h3>
            <ClientForm initialValues={client} onSubmit={handleUpdate} submitting={saving} showClientId={false} />
          </div>
        </div>
      )}

      {tab === "contracts" && (
        <DataTable
          data={contracts}
          columns={contractColumns}
          onRowClick={(row) => navigate(`/crm/contracts/${row.contract_id ?? row.id}`)}
        />
      )}

      {tab === "subscriptions" && (
        <DataTable
          data={subscriptions}
          columns={subscriptionColumns}
          onRowClick={(row) => navigate(`/crm/subscriptions/${row.subscription_id ?? row.id}`)}
        />
      )}

      {tab === "features" && (
        <FeatureFlagsPanel flags={features} onToggle={handleToggleFeature} disabled={!canToggleFeatures} />
      )}

      {tab === "profiles" && (
        <div style={{ display: "grid", gap: 16 }}>
          <div>
            <div style={{ fontWeight: 600 }}>Assigned limit profile</div>
            <div>{client.limit_profile_id ?? "-"}</div>
          </div>
          <div>
            <div style={{ fontWeight: 600 }}>Assigned risk profile</div>
            <div>{client.risk_profile_id ?? "-"}</div>
          </div>
          <div>
            <details>
              <summary>Available limit profiles</summary>
              <JsonViewer value={limitProfiles} />
            </details>
          </div>
          <div>
            <details>
              <summary>Available risk profiles</summary>
              <JsonViewer value={riskProfiles} />
            </details>
          </div>
        </div>
      )}
    </div>
  );
};

export default ClientDetailsPage;
