import { useMemo, useState } from "react";
import { request } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { Toast } from "../components/common/Toast";
import { useToast } from "../components/Toast/useToast";
import { withBase } from "@shared/lib/path";

const VIEW_OPTIONS = ["FULL", "FLEET", "ACCOUNTANT"] as const;
const SUBJECT_OPTIONS = [
  { value: "fuel_tx_id", label: "Fuel transaction" },
  { value: "order_id", label: "Order" },
  { value: "invoice_id", label: "Invoice" },
] as const;

type UnifiedExplainAction = {
  code: string;
  title: string;
  description: string;
  target?: string | null;
  severity: "INFO" | "REQUIRED";
  hint?: string | null;
  link?: string | null;
};

type UnifiedExplainPayload = {
  primary_reason: string;
  secondary_reasons: string[];
  subject: {
    type: string;
    id: string;
    ts?: string | null;
    client_id?: string | null;
  };
  ids: {
    risk_decision_id?: string | null;
    ledger_transaction_id?: string | null;
    invoice_id?: string | null;
    snapshot_id?: string | null;
    snapshot_hash?: string | null;
  };
  sections?: Record<string, unknown>;
  recommendations?: string[];
  actions?: UnifiedExplainAction[];
  sla?: {
    started_at: string;
    expires_at: string;
    remaining_minutes: number;
  } | null;
  escalation?: {
    target: string;
    status: string;
  } | null;
  assistant?: {
    primary_insight: string;
    action?: UnifiedExplainAction | null;
    action_effect_pct?: number | null;
    confidence: number;
    sla?: {
      started_at: string;
      expires_at: string;
      remaining_minutes: number;
    } | null;
    escalation?: {
      target: string;
      status: string;
    } | null;
    answers: Record<string, string>;
  } | null;
};

const parseIsoDate = (value?: string | null) => {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
};

const formatDateTime = (value?: string | null) => {
  if (!value) return "—";
  const parsed = parseIsoDate(value);
  if (!parsed) return value;
  return parsed.toLocaleString();
};

const getSlaTone = (sla?: UnifiedExplainPayload["sla"]) => {
  if (!sla) return "#94a3b8";
  const started = parseIsoDate(sla.started_at);
  const expires = parseIsoDate(sla.expires_at);
  if (!started || !expires) return "#94a3b8";
  const totalMinutes = Math.max(1, (expires.getTime() - started.getTime()) / 60000);
  const ratio = Math.max(0, Math.min(1, sla.remaining_minutes / totalMinutes));
  if (ratio >= 0.5) return "#16a34a";
  if (ratio >= 0.2) return "#f59e0b";
  return "#dc2626";
};

export const UnifiedExplainPage = () => {
  const { accessToken } = useAuth();
  const { toast, showToast } = useToast();
  const [subjectType, setSubjectType] = useState<(typeof SUBJECT_OPTIONS)[number]["value"]>("fuel_tx_id");
  const [subjectId, setSubjectId] = useState("");
  const [view, setView] = useState<(typeof VIEW_OPTIONS)[number]>("FULL");
  const [depth, setDepth] = useState(3);
  const [snapshot, setSnapshot] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [payload, setPayload] = useState<UnifiedExplainPayload | null>(null);
  const [showSecondaryAll, setShowSecondaryAll] = useState(false);
  const [confirmReplayLink, setConfirmReplayLink] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"explain" | "assistant">("explain");
  const [assistantQuestion, setAssistantQuestion] = useState<string>("why_problem");

  const canSubmit = subjectId.trim().length > 0;

  const query = useMemo(() => {
    const params = new URLSearchParams();
    params.set(subjectType, subjectId.trim());
    params.set("view", view);
    params.set("depth", String(depth));
    if (snapshot) {
      params.set("snapshot", "true");
    }
    return params.toString();
  }, [subjectId, subjectType, view, depth, snapshot]);

  const handleSubmit = async (forceSnapshot = false) => {
    if (!canSubmit) {
      return;
    }
    setError(null);
    setIsLoading(true);
    try {
      const snapshotParam = forceSnapshot ? "true" : snapshot ? "true" : undefined;
      const params = new URLSearchParams(query);
      if (snapshotParam) {
        params.set("snapshot", snapshotParam);
      }
      const data = await request<Record<string, unknown>>(`/explain?${params.toString()}`, {}, accessToken);
      setPayload(data as UnifiedExplainPayload);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Не удалось загрузить explain";
      setError(message);
      showToast("error", message);
    } finally {
      setIsLoading(false);
    }
  };

  const actions = payload?.actions ?? [];
  const secondaryReasons = payload?.secondary_reasons ?? [];
  const recommendations = payload?.recommendations ?? [];
  const visibleSecondary = showSecondaryAll ? secondaryReasons : secondaryReasons.slice(0, 2);
  const remainingSecondary = secondaryReasons.length - visibleSecondary.length;
  const assistant = payload?.assistant ?? null;
  const assistantAction = assistant?.action ?? null;
  const assistantQuestions = [
    { key: "why_problem", label: "Почему сейчас это проблема?" },
    { key: "if_ignore", label: "Что будет, если ничего не делать?" },
    { key: "first_action", label: "Что лучше сделать первым?" },
    { key: "trend", label: "Это ухудшается или стабильно?" },
  ];

  const limitSection = payload?.sections?.limits as { limit_profiles?: unknown[]; profiles?: unknown[] } | undefined;
  const hasLimitProfiles = Boolean(limitSection?.limit_profiles?.length || limitSection?.profiles?.length);

  const getReplayScope = () => {
    if (payload?.ids?.invoice_id) return "SUBSCRIPTIONS";
    if (payload?.subject?.type === "FUEL_TX") return "FUEL";
    return "ALL";
  };

  const getPeriodId = () => {
    const moneySection = payload?.sections?.money as
      | { period_id?: string; billing_period_id?: string; period?: { id?: string } }
      | undefined;
    return moneySection?.period_id || moneySection?.billing_period_id || moneySection?.period?.id || null;
  };

  const moneySummary = payload?.sections?.money as
    | {
        charged?: number;
        paid?: number;
        due?: number;
        refunded?: number;
        invariants?: string;
        replay_link?: string | null;
      }
    | undefined;
  const crmSection = payload?.sections?.crm as
    | {
        tariff?: string | null;
        subscription_status?: string | null;
        metrics_used?: Record<string, number>;
        feature_flags?: Record<string, boolean>;
        decision_flags?: string[];
        contract?: { id: string; version: number } | null;
        decision_basis?: string | null;
      }
    | undefined;
  const orderId =
    payload?.subject?.type === "ORDER"
      ? payload?.subject?.id
      : (payload?.sections?.logistics as { order_id?: string } | undefined)?.order_id ?? null;
  const deepLinks = [
    {
      label: "CRM",
      url: payload?.subject?.client_id ? `/crm/clients/${payload.subject.client_id}` : null,
    },
    {
      label: "Money",
      url: payload?.ids?.invoice_id ? `/money/invoice-cfo-explain?invoice_id=${payload.ids.invoice_id}` : null,
    },
    {
      label: "Logistics",
      url: orderId ? `/logistics/orders/${orderId}` : null,
    },
  ];

  const resolveActionLink = (action: UnifiedExplainAction) => {
    const clientId = payload?.subject?.client_id;
    const invoiceId = payload?.ids?.invoice_id;
    const orderId = payload?.subject?.type === "ORDER" ? payload?.subject?.id : null;
    const periodId = getPeriodId();

    switch (action.code) {
      case "INCREASE_LIMIT":
        if (!clientId) return { url: "", missing: "client" };
        return {
          url: `/crm/clients/${clientId}?tab=${hasLimitProfiles ? "profiles" : "features"}`,
          missing: null,
        };
      case "REQUEST_OVERRIDE":
        return { url: invoiceId ? `/money/invoice-cfo-explain?invoice_id=${invoiceId}` : "/money/health", missing: null };
      case "ADJUST_ROUTE":
        if (!orderId) return { url: "", missing: "order" };
        return { url: `/explain?order_id=${orderId}`, missing: null };
      case "RUN_REPLAY":
        if (!clientId) return { url: "", missing: "client" };
        if (!periodId) return { url: "", missing: "period" };
        return {
          url: `/money/replay?client_id=${clientId}&period_id=${periodId}&scope=${getReplayScope()}&mode=COMPARE`,
          missing: null,
        };
      default:
        return { url: "", missing: "action" };
    }
  };

  const handleActionClick = (action: UnifiedExplainAction) => {
    const { url, missing } = resolveActionLink(action);
    if (!url || missing) return;
    const targetUrl = withBase(url);
    if (action.code === "RUN_REPLAY") {
      setConfirmReplayLink(targetUrl);
      return;
    }
    window.location.assign(targetUrl);
  };

  const handleCopy = async () => {
    if (!payload) return;
    const copyText = `primary_reason: ${payload.primary_reason}\nids: ${JSON.stringify(payload.ids, null, 2)}`;
    try {
      await navigator.clipboard.writeText(copyText);
      showToast("success", "Copied to clipboard");
    } catch (err) {
      showToast("error", err instanceof Error ? err.message : "Не удалось скопировать");
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Toast toast={toast} />
      <div>
        <h1 style={{ fontSize: 24, fontWeight: 700 }}>Unified Explain</h1>
        <p style={{ color: "#475569" }}>
          Поиск причин отказа/рисков для fuel, order или invoice.
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span>Subject type</span>
          <select value={subjectType} onChange={(event) => setSubjectType(event.target.value as typeof subjectType)}>
            {SUBJECT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span>ID</span>
          <input
            type="text"
            value={subjectId}
            placeholder="Введите ID"
            onChange={(event) => setSubjectId(event.target.value)}
          />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span>View</span>
          <select value={view} onChange={(event) => setView(event.target.value as typeof view)}>
            {VIEW_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span>Depth</span>
          <input
            type="number"
            min={1}
            max={5}
            value={depth}
            onChange={(event) => setDepth(Number(event.target.value))}
          />
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 24 }}>
          <input type="checkbox" checked={snapshot} onChange={(event) => setSnapshot(event.target.checked)} />
          Создать snapshot
        </label>
      </div>

      <div style={{ display: "flex", gap: 12 }}>
        <button
          onClick={() => handleSubmit(false)}
          disabled={!canSubmit || isLoading}
          style={{ padding: "10px 16px", borderRadius: 8, border: "1px solid #cbd5e1" }}
        >
          {isLoading ? "Загрузка..." : "Получить объяснение"}
        </button>
        <button
          onClick={() => handleSubmit(true)}
          disabled={!canSubmit || isLoading}
          style={{ padding: "10px 16px", borderRadius: 8, border: "1px solid #cbd5e1" }}
        >
          Create snapshot
        </button>
      </div>

      {error ? (
        <div style={{ color: "#b91c1c", background: "#fee2e2", padding: 12, borderRadius: 8 }}>{error}</div>
      ) : null}

      {payload ? (
        <div style={{ display: "grid", gap: 16, background: "#fff", borderRadius: 12, padding: 16 }}>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              onClick={() => setActiveTab("explain")}
              style={{
                padding: "6px 12px",
                borderRadius: 999,
                border: "1px solid #cbd5e1",
                background: activeTab === "explain" ? "#2563eb" : "#fff",
                color: activeTab === "explain" ? "#f8fafc" : "#0f172a",
                fontWeight: 600,
              }}
            >
              Explain
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("assistant")}
              style={{
                padding: "6px 12px",
                borderRadius: 999,
                border: "1px solid #cbd5e1",
                background: activeTab === "assistant" ? "#2563eb" : "#fff",
                color: activeTab === "assistant" ? "#f8fafc" : "#0f172a",
                fontWeight: 600,
              }}
            >
              Assistant
            </button>
          </div>

          {activeTab === "explain" ? (
            <div style={{ display: "grid", gap: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                <span
                  style={{
                    background: "#2563eb",
                    color: "#f8fafc",
                    padding: "4px 10px",
                    borderRadius: 999,
                    fontWeight: 600,
                  }}
                >
                  {payload.primary_reason}
                </span>
                <span style={{ fontSize: 12, color: "#475569", fontWeight: 600 }}>PRIMARY</span>
                <button
                  type="button"
                  onClick={handleCopy}
                  style={{ padding: "6px 10px", borderRadius: 8, border: "1px solid #cbd5e1" }}
                >
                  Copy reason + ids
                </button>
              </div>

              <div>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>Secondary reasons</div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {visibleSecondary.length ? (
                    visibleSecondary.map((reason) => (
                      <span
                        key={reason}
                        style={{
                          padding: "4px 10px",
                          borderRadius: 999,
                          background: "#e2e8f0",
                          color: "#0f172a",
                          fontSize: 12,
                        }}
                      >
                        {reason}
                      </span>
                    ))
                  ) : (
                    <span style={{ color: "#64748b" }}>Нет дополнительных причин</span>
                  )}
                  {remainingSecondary > 0 ? (
                    <button
                      type="button"
                      onClick={() => setShowSecondaryAll((value) => !value)}
                      style={{ padding: "4px 10px", borderRadius: 999, border: "1px dashed #94a3b8" }}
                    >
                      {showSecondaryAll ? "Свернуть" : `+${remainingSecondary} еще`}
                    </button>
                  ) : null}
                </div>
              </div>

              <div style={{ display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
                <div style={{ background: "#f8fafc", padding: 12, borderRadius: 10 }}>
                  <div style={{ fontSize: 12, color: "#64748b" }}>Escalation target</div>
                  <div style={{ fontWeight: 600 }}>{payload.escalation?.target ?? "—"}</div>
                  <div style={{ fontSize: 12, color: "#64748b" }}>Status</div>
                  <div>{payload.escalation?.status ?? "—"}</div>
                </div>
                <div style={{ background: "#f8fafc", padding: 12, borderRadius: 10 }}>
                  <div style={{ fontSize: 12, color: "#64748b" }}>SLA countdown</div>
                  <div style={{ fontWeight: 700, color: getSlaTone(payload.sla) }}>
                    {payload.sla ? `${payload.sla.remaining_minutes} мин` : "—"}
                  </div>
                  <div style={{ fontSize: 12, color: "#64748b" }}>started_at</div>
                  <div>{formatDateTime(payload.sla?.started_at)}</div>
                  <div style={{ fontSize: 12, color: "#64748b" }}>expires_at</div>
                  <div>{formatDateTime(payload.sla?.expires_at)}</div>
                </div>
              </div>

              <div>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>Actions</div>
                {actions.length ? (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
                    {actions.map((action) => {
                      const { url, missing } = resolveActionLink(action);
                      const isDisabled = Boolean(missing);
                      return (
                        <button
                          key={action.code}
                          onClick={() => handleActionClick(action)}
                          disabled={isDisabled}
                          title={missing ? `missing ${missing}` : action.description}
                          style={{
                            padding: "10px 14px",
                            borderRadius: 10,
                            border: "1px solid #cbd5e1",
                            background: isDisabled ? "#e2e8f0" : "#fff",
                            color: isDisabled ? "#94a3b8" : "#0f172a",
                            cursor: isDisabled ? "not-allowed" : "pointer",
                            minWidth: 180,
                            textAlign: "left",
                          }}
                        >
                          <div style={{ fontWeight: 600 }}>{action.title}</div>
                          <div style={{ fontSize: 12, color: "#64748b" }}>{action.description}</div>
                          {url && !isDisabled ? (
                            <div style={{ fontSize: 11, color: "#2563eb", marginTop: 4 }}>{url}</div>
                          ) : null}
                        </button>
                      );
                    })}
                  </div>
                ) : (
                  <div style={{ color: "#64748b" }}>Нет доступных действий</div>
                )}
              </div>

              <div>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>Recommendations</div>
                {recommendations.length ? (
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {recommendations.map((rec) => (
                      <li key={rec}>{rec}</li>
                    ))}
                  </ul>
                ) : (
                  <div style={{ color: "#64748b" }}>Нет рекомендаций</div>
                )}
              </div>

              {moneySummary ? (
                <div style={{ background: "#f8fafc", padding: 12, borderRadius: 10 }}>
                  <div style={{ fontWeight: 600, marginBottom: 8 }}>Money summary</div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 8 }}>
                    <div>
                      <div style={{ fontSize: 12, color: "#64748b" }}>Charged</div>
                      <div>{moneySummary.charged ?? "—"}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 12, color: "#64748b" }}>Paid</div>
                      <div>{moneySummary.paid ?? "—"}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 12, color: "#64748b" }}>Due</div>
                      <div>{moneySummary.due ?? "—"}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 12, color: "#64748b" }}>Refunded</div>
                      <div>{moneySummary.refunded ?? "—"}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 12, color: "#64748b" }}>Invariants</div>
                      <div>{moneySummary.invariants ?? "—"}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 12, color: "#64748b" }}>Replay</div>
                      <div>{moneySummary.replay_link ?? "—"}</div>
                    </div>
                  </div>
                </div>
              ) : null}

              {crmSection ? (
                <div style={{ background: "#f8fafc", padding: 12, borderRadius: 10 }}>
                  <div style={{ fontWeight: 600, marginBottom: 8 }}>CRM</div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 8 }}>
                    <div>
                      <div style={{ fontSize: 12, color: "#64748b" }}>Tariff</div>
                      <div>{crmSection.tariff ?? "—"}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 12, color: "#64748b" }}>Subscription</div>
                      <div>{crmSection.subscription_status ?? "—"}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: 12, color: "#64748b" }}>Contract</div>
                      <div>
                        {crmSection.contract?.id ?? "—"}
                        {crmSection.contract?.version ? ` · v${crmSection.contract.version}` : ""}
                      </div>
                    </div>
                    <div>
                      <div style={{ fontSize: 12, color: "#64748b" }}>Decision basis</div>
                      <div>{crmSection.decision_basis ?? "—"}</div>
                    </div>
                  </div>
                  <div style={{ marginTop: 12 }}>
                    <div style={{ fontSize: 12, color: "#64748b" }}>Metrics used</div>
                    <pre style={{ margin: 0 }}>{JSON.stringify(crmSection.metrics_used ?? {}, null, 2)}</pre>
                  </div>
                  <div style={{ marginTop: 12 }}>
                    <div style={{ fontSize: 12, color: "#64748b" }}>Feature flags</div>
                    <pre style={{ margin: 0 }}>{JSON.stringify(crmSection.feature_flags ?? {}, null, 2)}</pre>
                  </div>
                  <div style={{ marginTop: 12 }}>
                    <div style={{ fontSize: 12, color: "#64748b" }}>Decision flags</div>
                    <div>{crmSection.decision_flags?.length ? crmSection.decision_flags.join(", ") : "—"}</div>
                  </div>
                </div>
              ) : null}

              <div>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>Deeplinks</div>
                <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                  {deepLinks.map((link) => (
                    <a
                      key={link.label}
                      href={link.url ? withBase(link.url) : "#"}
                      style={{
                        padding: "6px 10px",
                        borderRadius: 8,
                        border: "1px solid #cbd5e1",
                        color: link.url ? "#2563eb" : "#94a3b8",
                        pointerEvents: link.url ? "auto" : "none",
                      }}
                    >
                      {link.label}
                    </a>
                  ))}
                </div>
              </div>

              <div style={{ background: "#0f172a", color: "#f8fafc", padding: 16, borderRadius: 12 }}>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>Ответ</div>
                <pre style={{ whiteSpace: "pre-wrap", margin: 0 }}>
                  {payload ? JSON.stringify(payload, null, 2) : "Нет данных"}
                </pre>
              </div>
            </div>
          ) : (
            <div style={{ display: "grid", gap: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                <span style={{ fontWeight: 700 }}>Primary insight</span>
                <span style={{ color: "#475569" }}>{assistant?.primary_insight ?? "Нет данных"}</span>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 8 }}>
                <div style={{ background: "#f8fafc", padding: 12, borderRadius: 10 }}>
                  <div style={{ fontSize: 12, color: "#64748b" }}>Confidence</div>
                  <div style={{ fontWeight: 700 }}>{assistant ? `${assistant.confidence}%` : "—"}</div>
                </div>
                <div style={{ background: "#f8fafc", padding: 12, borderRadius: 10 }}>
                  <div style={{ fontSize: 12, color: "#64748b" }}>SLA</div>
                  <div style={{ fontWeight: 700, color: getSlaTone(assistant?.sla) }}>
                    {assistant?.sla ? `${assistant.sla.remaining_minutes} мин` : "—"}
                  </div>
                  <div style={{ fontSize: 12, color: "#64748b" }}>Escalation</div>
                  <div>{assistant?.escalation?.target ?? "—"}</div>
                </div>
                <div style={{ background: "#f8fafc", padding: 12, borderRadius: 10 }}>
                  <div style={{ fontSize: 12, color: "#64748b" }}>Action</div>
                  <div style={{ fontWeight: 700 }}>{assistantAction?.title ?? "—"}</div>
                  {assistantAction ? (
                    <button
                      type="button"
                      onClick={() => handleActionClick(assistantAction as UnifiedExplainAction)}
                      disabled={Boolean(resolveActionLink(assistantAction as UnifiedExplainAction).missing)}
                      style={{ marginTop: 6, padding: "6px 10px", borderRadius: 8, border: "1px solid #cbd5e1" }}
                    >
                      Перейти к действию
                    </button>
                  ) : null}
                </div>
              </div>
              <div>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>Готовые вопросы</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {assistantQuestions.map((question) => (
                    <button
                      key={question.key}
                      type="button"
                      onClick={() => setAssistantQuestion(question.key)}
                      style={{
                        padding: "6px 12px",
                        borderRadius: 999,
                        border: "1px solid #cbd5e1",
                        background: assistantQuestion === question.key ? "#2563eb" : "#fff",
                        color: assistantQuestion === question.key ? "#f8fafc" : "#0f172a",
                      }}
                    >
                      {question.label}
                    </button>
                  ))}
                </div>
              </div>
              <div style={{ background: "#f8fafc", padding: 12, borderRadius: 10, minHeight: 120 }}>
                {assistant?.answers?.[assistantQuestion] ?? "Ответ будет доступен после загрузки snapshot."}
              </div>
            </div>
          )}
        </div>
      ) : null}

      {confirmReplayLink ? (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(15, 23, 42, 0.6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 20,
          }}
        >
          <div style={{ background: "#fff", padding: 24, borderRadius: 12, width: 420 }}>
            <h3 style={{ marginTop: 0 }}>Run replay?</h3>
            <p style={{ color: "#475569" }}>Операция запускает replay сравнения. Продолжить?</p>
            <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
              <button
                type="button"
                onClick={() => setConfirmReplayLink(null)}
                style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #cbd5e1" }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  const link = confirmReplayLink;
                  setConfirmReplayLink(null);
                  window.location.assign(link);
                }}
                style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid #0f172a", background: "#0f172a", color: "#fff" }}
              >
                Run replay
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default UnifiedExplainPage;
