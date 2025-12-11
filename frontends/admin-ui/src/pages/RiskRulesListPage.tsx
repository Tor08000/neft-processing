import React, { Suspense, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchRiskRules } from "../api/riskRules";
import { Loader } from "../components/Loader/Loader";
import { Table, type Column } from "../components/Table/Table";
import { formatDateTime } from "../utils/format";
import { type RiskRule, type RiskRulesQuery } from "../types/riskRules";

const SCOPES = ["GLOBAL", "CLIENT", "CARD", "TARIFF"] as const;

export const RiskRulesListPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [scope, setScope] = useState<string>(searchParams.get("scope") || "ANY");
  const [enabled, setEnabled] = useState<string>(searchParams.get("enabled") || "ANY");
  const [subjectId, setSubjectId] = useState<string>(searchParams.get("subject_id") || "");
  const [reason, setReason] = useState<string>(searchParams.get("reason") || "");
  const [limit] = useState<number>(20);
  const [offset, setOffset] = useState<number>(0);

  useEffect(() => {
    const params: Record<string, string> = {};
    if (scope !== "ANY") params.scope = scope;
    if (enabled !== "ANY") params.enabled = enabled;
    if (subjectId) params.subject_id = subjectId;
    if (reason) params.reason = reason;
    setSearchParams(params, { replace: true });
  }, [enabled, reason, scope, setSearchParams, subjectId]);

  const filters = useMemo<RiskRulesQuery>(
    () => ({
      limit,
      offset,
      scope: scope !== "ANY" ? (scope as RiskRulesQuery["scope"]) : undefined,
      enabled: enabled === "ANY" ? undefined : enabled === "true",
      subject_id: subjectId || undefined,
      reason: reason || undefined,
    }),
    [enabled, limit, offset, reason, scope, subjectId],
  );

  const { data, isFetching, isLoading, error } = useQuery({
    queryKey: ["risk-rules", filters],
    queryFn: () => fetchRiskRules(filters),
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });

  const columns: Column<RiskRule>[] = [
    {
      key: "name",
      title: "Name",
      render: (row) => (
        <button
          type="button"
          onClick={() => navigate(`/risk/rules/${row.id}`)}
          style={{ background: "none", border: "none", color: "#2563eb", cursor: "pointer" }}
        >
          {row.dsl.name}
        </button>
      ),
    },
    { key: "scope", title: "Scope", render: (row) => row.dsl.scope },
    {
      key: "subject",
      title: "Subject",
      render: (row) => row.dsl.subject_id || "—",
    },
    { key: "action", title: "Action", render: (row) => row.dsl.action },
    { key: "enabled", title: "Enabled", render: (row) => (row.enabled ? "Yes" : "No") },
    { key: "updated_at", title: "Updated", render: (row) => formatDateTime(row.updated_at) },
  ];

  return (
    <div>
      <div className="page-header">
        <h1>Risk rules</h1>
        {(isLoading || isFetching) && <Loader label="Загружаем правила" />}
        {error && <span style={{ color: "#dc2626" }}>{(error as Error).message}</span>}
      </div>

      <div className="filters">
        <div className="filter">
          <span className="label">Scope</span>
          <select value={scope} onChange={(e) => setScope(e.target.value)}>
            <option value="ANY">Любой</option>
            {SCOPES.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>
        <div className="filter">
          <span className="label">Enabled</span>
          <select value={enabled} onChange={(e) => setEnabled(e.target.value)}>
            <option value="ANY">Любой</option>
            <option value="true">Включено</option>
            <option value="false">Выключено</option>
          </select>
        </div>
        <div className="filter">
          <span className="label">Subject</span>
          <input value={subjectId} onChange={(e) => setSubjectId(e.target.value)} placeholder="client / tariff" />
        </div>
        <div className="filter">
          <span className="label">Reason</span>
          <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="velocity / geo" />
        </div>
      </div>

      <Suspense fallback={<Loader label="Загружаем список" />}>
        <Table columns={columns} data={data?.items ?? []} />
      </Suspense>

      {data && data.total > limit && (
        <div style={{ marginTop: 12 }}>
          <div className="pagination">
            <button onClick={() => setOffset(Math.max(0, offset - limit))} disabled={offset === 0}>
              Prev
            </button>
            <span style={{ padding: "0 8px" }}>
              {(offset / limit) + 1} / {Math.ceil(data.total / limit)}
            </span>
            <button
              onClick={() => setOffset(Math.min(data.total - limit, offset + limit))}
              disabled={offset + limit >= data.total}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default RiskRulesListPage;
