import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  disableRiskRule,
  enableRiskRule,
  fetchRiskRule,
  updateRiskRule,
} from "../api/riskRules";
import { Loader } from "../components/Loader/Loader";
import { type RiskRule, type RiskRulePayload, type RuleConfig } from "../types/riskRules";

const METRICS: RuleConfig["metric"][] = [
  "always",
  "amount",
  "quantity",
  "count",
  "total_amount",
  "amount_spike",
  "unusual_product",
];

const ACTIONS: RuleConfig["action"][] = ["LOW", "MEDIUM", "HIGH", "MANUAL_REVIEW", "BLOCK"];

const SCOPES: RuleConfig["scope"][] = ["GLOBAL", "CLIENT", "CARD", "TARIFF"];

function toCommaString(value?: string[] | null): string {
  return value?.join(", ") ?? "";
}

function parseCommaSeparated(value: string): string[] | null {
  const normalized = value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  return normalized.length ? normalized : null;
}

export const RiskRuleDetailsPage: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<RuleConfig | null>(null);
  const [description, setDescription] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const { data: rule, isFetching, isLoading, error } = useQuery({
    queryKey: ["risk-rule", id],
    queryFn: () => fetchRiskRule(id as string),
    enabled: Boolean(id),
    staleTime: 30_000,
  });

  useEffect(() => {
    if (!rule) return;
    const cloned: RuleConfig = JSON.parse(JSON.stringify(rule.dsl));
    setDraft(cloned);
    setDescription(rule.description || "");
  }, [rule]);

  const mutation = useMutation({
    mutationFn: (payload: RiskRulePayload) => updateRiskRule(id as string, payload),
    onSuccess: (updated) => {
      queryClient.setQueryData(["risk-rule", id], updated);
      queryClient.invalidateQueries({ queryKey: ["risk-rules"] });
      setErrorMessage(null);
    },
    onError: (err) => setErrorMessage((err as Error).message),
  });

  const enableToggle = useMutation({
    mutationFn: (current: RiskRule) => (current.enabled ? disableRiskRule(current.id) : enableRiskRule(current.id)),
    onSuccess: (updated) => {
      queryClient.setQueryData(["risk-rule", id], updated);
      queryClient.invalidateQueries({ queryKey: ["risk-rules"] });
    },
    onError: (err) => setErrorMessage((err as Error).message),
  });

  const selector = useMemo(() => draft?.selector ?? { merchant_ids: [], terminal_ids: [], geo: [] }, [draft?.selector]);

  const windowConfig = draft?.window || { duration_seconds: undefined, hours: undefined };

  const handleSave = () => {
    if (!draft) return;
    const payload: RiskRulePayload = {
      description,
      dsl: {
        ...draft,
        selector: {
          ...draft.selector,
          product_types: parseCommaSeparated(toCommaString(selector.product_types || null)),
          merchant_ids: parseCommaSeparated(toCommaString(selector.merchant_ids || null)),
          terminal_ids: parseCommaSeparated(toCommaString(selector.terminal_ids || null)),
          geo: parseCommaSeparated(toCommaString(selector.geo || null)),
          hours: selector.hours ?? null,
        },
        window: windowConfig,
      },
    };
    mutation.mutate(payload);
  };

  return (
    <div>
      <div className="page-header">
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button onClick={() => navigate(-1)} style={{ padding: "6px 8px" }}>
            ← Назад
          </button>
          <h1>Rule details</h1>
        </div>
        {(isLoading || isFetching || mutation.isPending || enableToggle.isPending) && <Loader label="Сохраняем" />}
        {(error || errorMessage) && (
          <span style={{ color: "#dc2626" }}>{(error as Error)?.message || errorMessage}</span>
        )}
      </div>

      {!rule && (isLoading || isFetching) && <Loader label="Загружаем правило" />}

      {rule && draft && (
        <div className="card" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12 }}>
            <label className="label">
              Name
              <input
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                required
              />
            </label>
            <label className="label">
              Description
              <input value={description} onChange={(e) => setDescription(e.target.value)} />
            </label>
            <label className="label">
              Scope
              <select
                value={draft.scope}
                onChange={(e) => setDraft({ ...draft, scope: e.target.value as RuleConfig["scope"] })}
              >
                {SCOPES.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>
            <label className="label">
              Subject ID
              <input
                value={draft.subject_id ?? ""}
                onChange={(e) => setDraft({ ...draft, subject_id: e.target.value || null })}
                placeholder="client / card / tariff"
              />
            </label>
            <label className="label">
              Metric
              <select
                value={draft.metric}
                onChange={(e) => setDraft({ ...draft, metric: e.target.value as RuleConfig["metric"] })}
              >
                {METRICS.map((metric) => (
                  <option key={metric} value={metric}>
                    {metric}
                  </option>
                ))}
              </select>
            </label>
            <label className="label">
              Action
              <select
                value={draft.action}
                onChange={(e) => setDraft({ ...draft, action: e.target.value as RuleConfig["action"] })}
              >
                {ACTIONS.map((action) => (
                  <option key={action} value={action}>
                    {action}
                  </option>
                ))}
              </select>
            </label>
            <label className="label">
              Value / threshold
              <input
                type="number"
                step="0.01"
                value={draft.value}
                onChange={(e) => setDraft({ ...draft, value: Number(e.target.value) })}
              />
            </label>
            <label className="label">
              Priority
              <input
                type="number"
                value={draft.priority ?? 0}
                onChange={(e) => setDraft({ ...draft, priority: Number(e.target.value) })}
              />
            </label>
          </div>

          <div className="card" style={{ background: "#f8fafc" }}>
            <h3>Selector</h3>
            <div className="filters" style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))" }}>
              <div className="filter">
                <span className="label">Merchants</span>
                <input
                  value={toCommaString(selector.merchant_ids)}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      selector: { ...selector, merchant_ids: parseCommaSeparated(e.target.value) },
                    })
                  }
                  placeholder="M-1, M-2"
                />
              </div>
              <div className="filter">
                <span className="label">Terminals</span>
                <input
                  value={toCommaString(selector.terminal_ids)}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      selector: { ...selector, terminal_ids: parseCommaSeparated(e.target.value) },
                    })
                  }
                  placeholder="T-1, T-2"
                />
              </div>
              <div className="filter">
                <span className="label">Geo</span>
                <input
                  value={toCommaString(selector.geo)}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      selector: { ...selector, geo: parseCommaSeparated(e.target.value) },
                    })
                  }
                  placeholder="KZ, RU"
                />
              </div>
              <div className="filter">
                <span className="label">Hours (0-23)</span>
                <input
                  value={(selector.hours || []).join(", ")}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      selector: {
                        ...selector,
                        hours:
                          e.target.value.trim() === ""
                            ? null
                            : e.target.value
                                .split(",")
                                .map((item) => Number(item.trim()))
                                .filter((num) => !Number.isNaN(num)),
                      },
                    })
                  }
                  placeholder="0, 1, 2"
                />
              </div>
            </div>
          </div>

          <div className="card" style={{ background: "#f8fafc" }}>
            <h3>Window (optional)</h3>
            <div className="filters" style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))" }}>
              <div className="filter">
                <span className="label">Duration seconds</span>
                <input
                  type="number"
                  min={0}
                  value={windowConfig.duration_seconds ?? ""}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      window: {
                        ...windowConfig,
                        duration_seconds: e.target.value ? Number(e.target.value) : undefined,
                      },
                    })
                  }
                />
              </div>
              <div className="filter">
                <span className="label">Hours</span>
                <input
                  type="number"
                  min={0}
                  value={windowConfig.hours ?? ""}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      window: { ...windowConfig, hours: e.target.value ? Number(e.target.value) : undefined },
                    })
                  }
                />
              </div>
            </div>
          </div>

          <div className="card" style={{ background: "#f8fafc" }}>
            <h3>Flags</h3>
            <div className="filters" style={{ gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
              <div className="filter">
                <span className="label">Reason</span>
                <input
                  value={draft.reason ?? ""}
                  onChange={(e) => setDraft({ ...draft, reason: e.target.value || null })}
                  placeholder="velocity / ai"
                />
              </div>
              <div className="filter">
                <span className="label">Enabled</span>
                <select
                  value={draft.enabled ? "true" : "false"}
                  onChange={(e) => setDraft({ ...draft, enabled: e.target.value === "true" })}
                >
                  <option value="true">Enabled</option>
                  <option value="false">Disabled</option>
                </select>
              </div>
              <div className="filter">
                <span className="label">Version</span>
                <input value={rule.version} readOnly />
              </div>
            </div>
          </div>

          <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
            <button
              onClick={() => rule && enableToggle.mutate(rule)}
              disabled={enableToggle.isPending || mutation.isPending}
            >
              {rule?.enabled ? "Выключить" : "Включить"}
            </button>
            <button onClick={handleSave} disabled={mutation.isPending} style={{ background: "#2563eb", color: "#fff" }}>
              Сохранить
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default RiskRuleDetailsPage;
