import React, { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { evaluateRulesSandbox, fetchRuleSetVersions, type SandboxResponse } from "../api/unifiedRules";

const SCOPES = ["API", "FLEET", "DOCS", "BILLING", "MARKETPLACE", "AUTH", "CRM", "GLOBAL"] as const;

const PRESETS = {
  fleet_daily_spend: {
    label: "Fleet: Daily spend",
    scope: "FLEET",
    context: { client_id: "c1", card_id: "card1", amount: 12000, currency: "RUB", endpoint: null, ip: "1.2.3.4" },
    synthetic_metrics: { AMOUNT: 50000 },
  },
  api_rate: {
    label: "API: Rate check",
    scope: "API",
    context: { endpoint: "/v1/orders", ip: "10.0.0.1" },
    synthetic_metrics: { COUNT: 120 },
  },
} as const;

type PresetKey = keyof typeof PRESETS;

export const RulesSandboxPage: React.FC = () => {
  const [mode, setMode] = useState<"synthetic" | "historical">("synthetic");
  const [scope, setScope] = useState<string>("FLEET");
  const [versionId, setVersionId] = useState<string>("");
  const [presetKey, setPresetKey] = useState<PresetKey>("fleet_daily_spend");
  const [contextText, setContextText] = useState<string>(JSON.stringify(PRESETS.fleet_daily_spend.context, null, 2));
  const [metricsText, setMetricsText] = useState<string>(JSON.stringify(PRESETS.fleet_daily_spend.synthetic_metrics, null, 2));
  const [transactionId, setTransactionId] = useState<string>("");
  const [result, setResult] = useState<SandboxResponse | null>(null);
  const [error, setError] = useState<string>("");

  const { data: versions, isFetching } = useQuery({
    queryKey: ["ruleset-versions", scope],
    queryFn: () => fetchRuleSetVersions(scope),
    staleTime: 30_000,
  });

  const versionOptions = useMemo(() => versions ?? [], [versions]);

  const handlePresetChange = (nextKey: PresetKey) => {
    const preset = PRESETS[nextKey];
    setPresetKey(nextKey);
    setScope(preset.scope);
    setContextText(JSON.stringify(preset.context, null, 2));
    setMetricsText(JSON.stringify(preset.synthetic_metrics, null, 2));
  };

  const handleEvaluate = async () => {
    setError("");
    try {
      if (mode === "synthetic") {
        const context = JSON.parse(contextText);
        const synthetic_metrics = JSON.parse(metricsText);
        const payload = {
          mode,
          at: new Date().toISOString(),
          scope,
          context,
          synthetic_metrics,
          version_id: versionId ? Number(versionId) : undefined,
        };
        const response = await evaluateRulesSandbox(payload);
        setResult(response);
      } else {
        const payload = {
          mode,
          scope,
          transaction_id: transactionId,
          version_id: versionId ? Number(versionId) : undefined,
        };
        const response = await evaluateRulesSandbox(payload);
        setResult(response);
      }
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1>Rules sandbox</h1>
        {isFetching && <span>Загружаем версии...</span>}
      </div>

      <div className="neft-card" style={{ padding: 20, marginBottom: 16 }}>
        <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
          <label>
            <div className="label">Mode</div>
            <select className="neft-select" value={mode} onChange={(e) => setMode(e.target.value as typeof mode)}>
              <option value="synthetic">Synthetic</option>
              <option value="historical">Historical</option>
            </select>
          </label>
          <label>
            <div className="label">Scope</div>
            <select className="neft-select" value={scope} onChange={(e) => setScope(e.target.value)}>
              {SCOPES.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label>
            <div className="label">Rule set version</div>
            <select
              className="neft-select"
              value={versionId}
              onChange={(e) => setVersionId(e.target.value)}
            >
              <option value="">Active by scope</option>
              {versionOptions.map((version) => (
                <option key={version.id} value={version.id}>
                  {version.name} ({version.status})
                </option>
              ))}
            </select>
          </label>
          {mode === "synthetic" && (
            <label>
              <div className="label">Preset</div>
              <select
                className="neft-select"
                value={presetKey}
                onChange={(e) => handlePresetChange(e.target.value as PresetKey)}
              >
                {Object.entries(PRESETS).map(([key, preset]) => (
                  <option key={key} value={key}>
                    {preset.label}
                  </option>
                ))}
              </select>
            </label>
          )}
          {mode === "historical" && (
            <label>
              <div className="label">Transaction ID</div>
              <input
                className="neft-input"
                value={transactionId}
                onChange={(e) => setTransactionId(e.target.value)}
                placeholder="tx_123"
              />
            </label>
          )}
        </div>

        {mode === "synthetic" && (
          <div style={{ display: "grid", gap: 16, marginTop: 16, gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}>
            <label>
              <div className="label">Context (JSON)</div>
              <textarea
                className="neft-input"
                rows={8}
                value={contextText}
                onChange={(e) => setContextText(e.target.value)}
              />
            </label>
            <label>
              <div className="label">Synthetic metrics (JSON)</div>
              <textarea
                className="neft-input"
                rows={8}
                value={metricsText}
                onChange={(e) => setMetricsText(e.target.value)}
              />
            </label>
          </div>
        )}

        <div style={{ marginTop: 16, display: "flex", gap: 12, alignItems: "center" }}>
          <button className="neft-btn-primary" type="button" onClick={handleEvaluate}>
            Evaluate
          </button>
          {error && <span style={{ color: "#ff4d4d" }}>{error}</span>}
        </div>
      </div>

      {result && (
        <div className="neft-card" style={{ padding: 20 }}>
          <h2 style={{ marginTop: 0 }}>Decision</h2>
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
            <div>
              <div className="label">Decision</div>
              <div style={{ fontSize: 18 }}>{result.decision}</div>
            </div>
            <div>
              <div className="label">Reason codes</div>
              <div>{result.reason_codes.length ? result.reason_codes.join(", ") : "—"}</div>
            </div>
            <div>
              <div className="label">Rule set</div>
              <div>{result.version ? `${result.version.scope} / ${result.version.rule_set_version_id}` : "—"}</div>
            </div>
          </div>

          <h3 style={{ marginTop: 24 }}>Matched rules</h3>
          {result.matched_rules.length ? (
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left", padding: "8px 4px" }}>Code</th>
                  <th style={{ textAlign: "left", padding: "8px 4px" }}>Policy</th>
                  <th style={{ textAlign: "left", padding: "8px 4px" }}>Priority</th>
                  <th style={{ textAlign: "left", padding: "8px 4px" }}>Reason</th>
                  <th style={{ textAlign: "left", padding: "8px 4px" }}>Explain</th>
                </tr>
              </thead>
              <tbody>
                {result.matched_rules.map((rule) => (
                  <tr key={rule.code}>
                    <td style={{ padding: "6px 4px" }}>{rule.code}</td>
                    <td style={{ padding: "6px 4px" }}>{rule.policy}</td>
                    <td style={{ padding: "6px 4px" }}>{rule.priority}</td>
                    <td style={{ padding: "6px 4px" }}>{rule.reason_code ?? "—"}</td>
                    <td style={{ padding: "6px 4px" }}>{rule.explain ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div>Нет совпавших правил.</div>
          )}

          <details style={{ marginTop: 20 }}>
            <summary>Explain</summary>
            <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(result.explain, null, 2)}</pre>
          </details>
        </div>
      )}
    </div>
  );
};

export default RulesSandboxPage;
