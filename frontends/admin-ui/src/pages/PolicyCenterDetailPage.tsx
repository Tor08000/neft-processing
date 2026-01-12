import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  disablePolicy,
  enablePolicy,
  fetchPolicyDetail,
  fetchPolicyExecutions,
  type PolicyDetailResponse,
  type PolicyExecution,
  type PolicyHeader,
  type PolicyType,
} from "../api/policies";
import { useAuth } from "../auth/AuthContext";
import { DataTable, type DataColumn } from "../components/common/DataTable";
import { CopyButton } from "../components/CopyButton/CopyButton";
import { JsonViewer } from "../components/common/JsonViewer";
import { EmptyState as BrandEmptyState, StatusPill } from "@shared/brand/components";
import ForbiddenPage from "./ForbiddenPage";
import { describeError } from "../utils/apiErrors";
import { formatDateTime } from "../utils/format";

const statusTone = (status: PolicyHeader["status"]) => (status === "enabled" ? "success" : "neutral");

export const PolicyCenterDetailPage = () => {
  const { type, id } = useParams<{ type: PolicyType; id: string }>();
  const { accessToken } = useAuth();
  const [detail, setDetail] = useState<PolicyDetailResponse | null>(null);
  const [executions, setExecutions] = useState<PolicyExecution[]>([]);
  const [loading, setLoading] = useState(false);
  const [isForbidden, setIsForbidden] = useState(false);
  const [error, setError] = useState<{ title: string; description?: string; details?: string } | null>(null);
  const [toggling, setToggling] = useState(false);

  const loadDetail = useCallback(async () => {
    if (!accessToken || !type || !id) return;
    setLoading(true);
    setError(null);
    setIsForbidden(false);
    try {
      const [policyDetail, executionList] = await Promise.all([
        fetchPolicyDetail(accessToken, type, id),
        fetchPolicyExecutions(accessToken, type, id),
      ]);
      setDetail(policyDetail);
      setExecutions(executionList.items ?? []);
    } catch (err) {
      const summary = describeError(err);
      if (summary.isForbidden) {
        setIsForbidden(true);
        return;
      }
      setError({ title: "Не удалось загрузить политику", description: summary.message, details: summary.details });
    } finally {
      setLoading(false);
    }
  }, [accessToken, id, type]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  const handleToggle = useCallback(
    async (nextEnabled: boolean) => {
      if (!accessToken || !detail || !type || !id) return;
      setToggling(true);
      try {
        const updated = nextEnabled
          ? await enablePolicy(accessToken, type, id)
          : await disablePolicy(accessToken, type, id);
        setDetail({ ...detail, header: updated });
      } catch (err) {
        const summary = describeError(err);
        setError({ title: "Не удалось обновить статус политики", description: summary.message, details: summary.details });
      } finally {
        setToggling(false);
      }
    },
    [accessToken, detail, id, type],
  );

  const executionColumns = useMemo<DataColumn<PolicyExecution>[]>(
    () => [
      { key: "created_at", title: "Timestamp", render: (row) => formatDateTime(row.created_at) },
      { key: "event_type", title: "Event", render: (row) => row.event_type },
      { key: "action", title: "Action", render: (row) => row.action },
      { key: "status", title: "Status", render: (row) => row.status },
      { key: "event_id", title: "Event ID", render: (row) => row.event_id },
    ],
    [],
  );

  if (isForbidden) {
    return <ForbiddenPage />;
  }

  if (loading || !detail) {
    return (
      <div className="policy-detail">
        <div className="page-header">
          <h1>Policy</h1>
        </div>
        <DataTable data={[]} columns={executionColumns} loading />
      </div>
    );
  }

  const { header, policy, explain } = detail;
  const isEnabled = header.status === "enabled";

  return (
    <div className="policy-detail">
      <div className="page-header">
        <div>
          <h1>{header.title}</h1>
          <div className="muted">Policy ID: {header.id}</div>
        </div>
        <div className="policy-detail__actions">
          <Link className="button" to="/policies">
            Back to list
          </Link>
          <button
            type="button"
            className="button primary"
            disabled={!header.toggle_supported || toggling || isEnabled}
            onClick={() => void handleToggle(true)}
          >
            Enable
          </button>
          <button
            type="button"
            className="button"
            disabled={!header.toggle_supported || toggling || !isEnabled}
            onClick={() => void handleToggle(false)}
          >
            Disable
          </button>
          <CopyButton value={JSON.stringify(policy ?? {}, null, 2)} label="Copy JSON" />
        </div>
      </div>
      {error ? (
        <div className="card card--error">
          <strong>{error.title}</strong>
          <div>{error.description}</div>
        </div>
      ) : null}
      <section className="policy-summary card">
        <div>
          <div className="muted">Type</div>
          <div>{header.type.toUpperCase()}</div>
        </div>
        <div>
          <div className="muted">Status</div>
          <StatusPill tone={statusTone(header.status)}>{header.status}</StatusPill>
        </div>
        <div>
          <div className="muted">Scope</div>
          <div>
            {header.scope.tenant_id ? `Tenant ${header.scope.tenant_id}` : "Tenant —"}
            {header.scope.client_id ? ` · Client ${header.scope.client_id}` : " · Client —"}
          </div>
        </div>
        <div>
          <div className="muted">Updated</div>
          <div>{header.updated_at ? formatDateTime(header.updated_at) : "—"}</div>
        </div>
        <div className="policy-summary__actions">
          <div className="muted">Actions</div>
          <div className="pill-list">
            {header.actions.length ? (
              header.actions.map((action) => (
                <span key={action} className="pill pill--outline">
                  {action}
                </span>
              ))
            ) : (
              <span className="pill pill--neutral">No actions</span>
            )}
          </div>
        </div>
      </section>
      <section className="policy-section">
        <div className="policy-section__header">
          <h2>Explain</h2>
          <button className="button" type="button" disabled>
            View related cases
          </button>
        </div>
        {explain ? <JsonViewer value={explain} title="Explain payload" /> : <BrandEmptyState title="Explain not available" />}
      </section>
      <section className="policy-section">
        <h2>Definition</h2>
        {policy ? <JsonViewer value={policy} title="Policy JSON" /> : <BrandEmptyState title="No policy data" />}
      </section>
      <section className="policy-section">
        <h2>Executions</h2>
        {executions.length ? (
          <DataTable data={executions} columns={executionColumns} />
        ) : (
          <BrandEmptyState title="No executions found" description="No recent executions were recorded for this policy." />
        )}
      </section>
    </div>
  );
};

export default PolicyCenterDetailPage;
