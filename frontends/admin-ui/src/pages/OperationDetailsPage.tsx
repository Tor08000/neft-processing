import React, { Suspense, useMemo } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { fetchOperation, fetchOperationChildren, fetchOperations } from "../api/operations";
import { StatusBadge } from "../components/StatusBadge/StatusBadge";
import { RiskBadge } from "../components/RiskBadge/RiskBadge";
import { Table, type Column } from "../components/Table/Table";
import { formatAmount, formatDateTime } from "../utils/format";
import { Operation, RiskPayload } from "../types/operations";
import { Loader } from "../components/Loader/Loader";
import { withBase } from "@shared/lib/path";

export const OperationDetailsPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { data: operation, error, isLoading, isFetching } = useQuery({
    queryKey: ["operations", id],
    queryFn: () => fetchOperation(id as string),
    enabled: Boolean(id),
    staleTime: 30_000,
  });

  const { data: children = [], isFetching: isChildrenFetching } = useQuery({
    queryKey: ["operations", id, "children"],
    queryFn: () => fetchOperationChildren(id as string),
    enabled: Boolean(id),
    staleTime: 30_000,
  });

  const riskPayload = useMemo<RiskPayload | null>(() => {
    if (!operation?.risk_payload) return null;
    return operation.risk_payload as RiskPayload;
  }, [operation?.risk_payload]);

  const riskDecision = riskPayload?.decision;
  const riskReasons = operation?.risk_reasons || riskDecision?.reason_codes || [];
  const riskRules = operation?.risk_rules_fired || riskDecision?.rules_fired || [];
  const aiScore = riskDecision?.ai_score ?? null;
  const aiModelVersion = riskDecision?.ai_model_version ?? null;
  const riskSource = operation?.risk_source || riskPayload?.source || undefined;

  const dayRange = useMemo(() => {
    if (!operation?.created_at) return null;
    const date = new Date(operation.created_at);
    const from = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate(), 0, 0, 0));
    const to = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate(), 23, 59, 59, 999));
    return { from: from.toISOString(), to: to.toISOString() };
  }, [operation?.created_at]);

  const { data: cardOpsTotal } = useQuery({
    queryKey: ["operations", id, "card-count", operation?.card_id, dayRange?.from, dayRange?.to],
    queryFn: () =>
      fetchOperations({
        limit: 1,
        offset: 0,
        card_id: operation?.card_id || undefined,
        from_created_at: dayRange?.from,
        to_created_at: dayRange?.to,
      }).then((res) => res.total),
    enabled: Boolean(operation?.card_id && dayRange),
    staleTime: 30_000,
  });

  const { data: clientOpsTotal } = useQuery({
    queryKey: ["operations", id, "client-count", operation?.client_id, dayRange?.from, dayRange?.to],
    queryFn: () =>
      fetchOperations({
        limit: 1,
        offset: 0,
        client_id: operation?.client_id || undefined,
        from_created_at: dayRange?.from,
        to_created_at: dayRange?.to,
      }).then((res) => res.total),
    enabled: Boolean(operation?.client_id && dayRange),
    staleTime: 30_000,
  });

  const totals = useMemo(() => {
    const captured = children
      .filter((op) => op.operation_type === "CAPTURE")
      .reduce((acc, op) => acc + op.amount, 0);
    const refunded = children
      .filter((op) => op.operation_type === "REFUND")
      .reduce((acc, op) => acc + op.amount, 0);
    const authAmount = operation?.amount ?? 0;
    return {
      authAmount,
      captured,
      refunded,
      remaining: authAmount - captured + refunded,
    };
  }, [children, operation]);

  const columns: Column<Operation>[] = [
    { key: "id", title: "ID", render: (row) => row.operation_id },
    { key: "type", title: "Type", render: (row) => row.operation_type },
    { key: "status", title: "Status", render: (row) => <StatusBadge status={row.status} /> },
    { key: "amount", title: "Amount", render: (row) => formatAmount(row.amount) },
    { key: "created", title: "Created", render: (row) => formatDateTime(row.created_at) },
  ];

  return (
    <div>
      <div className="page-header">
        <h1>Operation details</h1>
        {(isLoading || isFetching || isChildrenFetching) && <Loader label="Загружаем операцию" />}
        {error && <span style={{ color: "var(--neft-error)" }}>{error.message}</span>}
        {operation ? (
          <div className="stack-inline">
            <Link className="ghost" to={`/explain?kind=operation&id=${encodeURIComponent(operation.operation_id)}`}>
              Explain
            </Link>
            <Link
              className="ghost"
              to={`/explain?kind=operation&id=${encodeURIComponent(operation.operation_id)}&diff=1`}
            >
              Сравнить
            </Link>
          </div>
        ) : null}
      </div>

      {operation && (
        <div className="card-grid" style={{ marginBottom: 16 }}>
          <div className="neft-card">
            <h3>{operation.operation_id}</h3>
            <p>
              <strong>Type:</strong> {operation.operation_type}
            </p>
            <p>
              <strong>Status:</strong> <StatusBadge status={operation.status} />
            </p>
            <p>
              <strong>Amount:</strong> {formatAmount(operation.amount)}
            </p>
            <p>
              <strong>Created:</strong> {formatDateTime(operation.created_at)}
            </p>
            <p>
              <strong>Merchant:</strong> {operation.merchant_id}
            </p>
          </div>
          <div className="neft-card">
            <h3>Aggregates</h3>
            <p>
              AUTH: <strong>{formatAmount(totals.authAmount)}</strong>
            </p>
            <p>
              Captured: <strong>{formatAmount(totals.captured)}</strong>
            </p>
            <p>
              Refunded: <strong>{formatAmount(totals.refunded)}</strong>
            </p>
            <p>
              Remaining: <strong>{formatAmount(totals.remaining)}</strong>
            </p>
          </div>
          <div className="neft-card">
            <h3>Risk</h3>
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
              <RiskBadge
                level={operation.risk_result || operation.risk_level}
                decision={operation.risk_level}
                score={operation.risk_score ?? undefined}
                reasons={riskReasons}
                source={riskSource}
              />
            </div>
            <p>
              <strong>Источник:</strong> {riskSource || "—"}
            </p>
            {riskReasons && riskReasons.length > 0 && (
              <div style={{ marginTop: 8 }}>
                <span className="label">Причины</span>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {riskReasons.map((reason) => (
                    <span key={reason} className="neft-chip neft-chip-info">
                      {reason}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {riskRules && riskRules.length > 0 && (
              <div style={{ marginTop: 8 }}>
                <span className="label">Сработавшие правила</span>
                <ul style={{ margin: "6px 0", paddingLeft: 18 }}>
                  {riskRules.map((rule) => {
                    const isId = /^\d+$/.test(String(rule));
                    return (
                      <li key={rule} style={{ color: "var(--neft-text-secondary)" }}>
                        {isId ? (
                          <a href={withBase(`/risk/rules/${rule}`)} style={{ color: "var(--neft-primary)" }}>
                            {rule}
                          </a>
                        ) : (
                          rule
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
            {(aiScore !== null || aiModelVersion) && (
              <div style={{ marginTop: 8 }}>
                <span className="label">AI</span>
                <div style={{ display: "flex", flexDirection: "column", gap: 4, color: "var(--neft-text-secondary)" }}>
                  {aiScore !== null && (
                    <span>
                      ai_score: <strong>{(aiScore * 100).toFixed(1)}</strong>
                    </span>
                  )}
                  {aiModelVersion && (
                    <span>
                      model_version: <strong>{aiModelVersion}</strong>
                    </span>
                  )}
                </div>
              </div>
            )}
            {operation.risk_flags && (
              <div style={{ marginTop: 8 }}>
                <span className="label">Флаги</span>
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  {Object.entries(operation.risk_flags).map(([key, value]) => (
                    <span key={key} style={{ color: "#334155" }}>
                      {key}: <strong>{String(value)}</strong>
                    </span>
                  ))}
                </div>
              </div>
            )}
            {(cardOpsTotal !== undefined || clientOpsTotal !== undefined) && (
              <div style={{ marginTop: 8 }}>
                <span className="label">Контекст за день</span>
                <div style={{ display: "flex", flexDirection: "column", gap: 4, color: "#334155" }}>
                  {cardOpsTotal !== undefined && (
                    <span>
                      Операций по карте: <strong>{cardOpsTotal}</strong>
                    </span>
                  )}
                  {clientOpsTotal !== undefined && (
                    <span>
                      Операций по клиенту: <strong>{clientOpsTotal}</strong>
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      <h2>Child operations</h2>
      <Suspense fallback={<Loader label="Загружаем операции" />}>
        <Table columns={columns} data={children} />
      </Suspense>
    </div>
  );
};

export default OperationDetailsPage;
