import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  disableFeature,
  enableFeature,
  getClient,
  getClientDecisionContext,
  getClientFeatures,
  listContracts,
  listLimitProfiles,
  listRiskProfiles,
  listSubscriptions,
  updateClient,
} from "../../api/crm";
import { ADMIN_API_BASE } from "../../api/base";
import { useAuth } from "../../auth/AuthContext";
import { DataTable, type DataColumn } from "../../components/common/DataTable";
import { EmptyState } from "../../components/common/EmptyState";
import { ErrorState } from "../../components/common/ErrorState";
import { JsonViewer } from "../../components/common/JsonViewer";
import { Loader } from "../../components/Loader/Loader";
import { Tabs } from "../../components/common/Tabs";
import { Toast } from "../../components/common/Toast";
import { ClientForm } from "../../components/crm/ClientForm";
import { FeatureFlagsPanel } from "../../components/crm/FeatureFlagsPanel";
import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import { useToast } from "../../components/Toast/useToast";
import type { CrmClient, CrmContract, CrmProfile, CrmSubscription } from "../../types/crm";
import { describeError, formatError } from "../../utils/apiErrors";

const EMPTY_VALUE = "-";

export const ClientDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [client, setClient] = useState<CrmClient | null>(null);
  const [contracts, setContracts] = useState<CrmContract[]>([]);
  const [subscriptions, setSubscriptions] = useState<CrmSubscription[]>([]);
  const [features, setFeatures] = useState<Record<string, boolean>>({});
  const [activeContractId, setActiveContractId] = useState<string | null>(null);
  const [limitProfileId, setLimitProfileId] = useState<string | null>(null);
  const [riskProfileId, setRiskProfileId] = useState<string | null>(null);
  const [limitProfiles, setLimitProfiles] = useState<CrmProfile[]>([]);
  const [riskProfiles, setRiskProfiles] = useState<CrmProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadErrorDetails, setLoadErrorDetails] = useState<string | undefined>(undefined);
  const [tab, setTab] = useState("overview");
  const [saving, setSaving] = useState(false);
  const [canToggleFeatures, setCanToggleFeatures] = useState(true);

  const loadClient = useCallback(() => {
    if (!accessToken || !id) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setLoadError(null);
    setLoadErrorDetails(undefined);
    setClient(null);
    setContracts([]);
    setSubscriptions([]);
    setFeatures({});
    setActiveContractId(null);
    setLimitProfileId(null);
    setRiskProfileId(null);
    setLimitProfiles([]);
    setRiskProfiles([]);
    Promise.all([
      getClient(accessToken, id),
      getClientDecisionContext(accessToken, id),
      listContracts(accessToken, { client_id: id }),
      listSubscriptions(accessToken, { client_id: id }),
      getClientFeatures(accessToken, id),
      listLimitProfiles(accessToken),
      listRiskProfiles(accessToken),
    ])
      .then(
        ([
          clientResponse,
          decisionContext,
          contractResponse,
          subscriptionResponse,
          featuresResponse,
          limitResponse,
          riskResponse,
        ]) => {
          setClient(clientResponse);
          setContracts(contractResponse.items);
          setSubscriptions(subscriptionResponse.items);
          setFeatures(featuresResponse ?? {});
          setActiveContractId(decisionContext.active_contract?.id ?? null);
          setLimitProfileId(decisionContext.limit_profile?.id ?? null);
          setRiskProfileId(decisionContext.risk_profile?.id ?? null);
          setLimitProfiles(limitResponse.items ?? []);
          setRiskProfiles(riskResponse.items ?? []);
        },
      )
      .catch((error: unknown) => {
        const summary = describeError(error);
        setLoadError(summary.message);
        setLoadErrorDetails(summary.details);
        showToast("error", formatError(error));
      })
      .finally(() => setLoading(false));
  }, [accessToken, id, showToast]);

  useEffect(() => {
    loadClient();
  }, [loadClient]);

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
      {
        key: "status",
        title: "Status",
        render: (row) => (row.status ? <StatusBadge status={row.status} /> : EMPTY_VALUE),
      },
      {
        key: "period",
        title: "Valid",
        render: (row) => `${row.valid_from ?? EMPTY_VALUE} -> ${row.valid_to ?? EMPTY_VALUE}`,
      },
      { key: "billing_mode", title: "Billing mode" },
      { key: "currency", title: "Currency" },
    ],
    [],
  );

  const subscriptionColumns: DataColumn<CrmSubscription>[] = useMemo(
    () => [
      { key: "subscription_id", title: "Subscription", render: (row) => row.id },
      {
        key: "status",
        title: "Status",
        render: (row) => (row.status ? <StatusBadge status={row.status} /> : EMPTY_VALUE),
      },
      { key: "tariff_plan_id", title: "Tariff" },
      { key: "billing_day", title: "Billing day" },
    ],
    [],
  );

  const activeSubscription = subscriptions.find((item) => item.status === "ACTIVE") ?? subscriptions[0] ?? null;
  const fleetReportLinks = client?.client_id
    ? [
        {
          label: "Driver behavior (7d)",
          href: `${ADMIN_API_BASE}/fleet-intelligence/drivers?client_id=${client.client_id}&window_days=7`,
        },
        {
          label: "Vehicle efficiency (7d)",
          href: `${ADMIN_API_BASE}/fleet-intelligence/vehicles?client_id=${client.client_id}&window_days=7`,
        },
        {
          label: "Station trust (7d)",
          href: `${ADMIN_API_BASE}/fleet-intelligence/stations?tenant_id=${client.tenant_id ?? 0}&window_days=7`,
        },
      ]
    : [];

  if (loading) {
    return <Loader label="Loading client detail" />;
  }

  if (!id) {
    return (
      <EmptyState
        title="Client ID is required"
        description="Open the client detail page from the CRM clients list."
        primaryAction={{ label: "Back to clients", onClick: () => navigate("/crm/clients") }}
      />
    );
  }

  if (loadError) {
    return (
      <ErrorState
        title="Failed to load client detail"
        description={loadError}
        details={loadErrorDetails}
        actionLabel="Retry"
        onAction={() => void loadClient()}
      />
    );
  }

  if (!client) {
    return (
      <EmptyState
        title="Client not found"
        description="The requested client is missing or no longer available."
        primaryAction={{ label: "Back to clients", onClick: () => navigate("/crm/clients") }}
      />
    );
  }

  return (
    <div>
      <Toast toast={toast} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1>Client {client.client_id}</h1>
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
            <div>Status: {client.status ? <StatusBadge status={client.status} /> : EMPTY_VALUE}</div>
            <div>Legal name: {client.legal_name ?? EMPTY_VALUE}</div>
            <div>Country: {client.country ?? EMPTY_VALUE}</div>
            <div>Timezone: {client.timezone ?? EMPTY_VALUE}</div>
            <div>Active contract: {activeContractId ?? EMPTY_VALUE}</div>
            <div>Active subscription: {activeSubscription?.id ?? EMPTY_VALUE}</div>
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
          onRowClick={(row) => navigate(`/crm/contracts/${row.id}`)}
        />
      )}

      {tab === "subscriptions" && (
        <DataTable
          data={subscriptions}
          columns={subscriptionColumns}
          onRowClick={(row) => navigate(`/crm/subscriptions/${row.id}`)}
        />
      )}

      {tab === "features" && (
        <FeatureFlagsPanel flags={features} onToggle={handleToggleFeature} disabled={!canToggleFeatures} />
      )}

      {tab === "profiles" && (
        <div style={{ display: "grid", gap: 16 }}>
          <div>
            <div style={{ fontWeight: 600 }}>Assigned limit profile</div>
            <div>{limitProfileId ?? EMPTY_VALUE}</div>
          </div>
          <div>
            <div style={{ fontWeight: 600 }}>Assigned risk profile</div>
            <div>{riskProfileId ?? EMPTY_VALUE}</div>
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
