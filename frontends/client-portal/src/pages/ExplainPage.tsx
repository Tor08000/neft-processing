import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { fetchExplainDiff, fetchExplainV2 } from "../api/explainV2";
import { useAuth } from "../auth/AuthContext";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";
import { AppEmptyState, AppErrorState, AppLoadingState } from "../components/states";
import { reduceExplainDiffReasons, type ExplainDiffTab } from "../features/explain/diffReducer";
import type {
  ExplainDiffResponse,
  ExplainEvidence,
  ExplainReasonNode,
  ExplainV2Response,
} from "../types/explainV2";

type EvidenceFilter = "all" | "linked";
const percent = (value?: number | null) => {
  if (value === null || value === undefined) return "—";
  return `${Math.round(value * 100)}%`;
};

const formatTimestamp = (value?: string | null) => {
  if (!value) return "—";
  const date = new Date(value);
  return date.toLocaleString("ru-RU");
};

const scoreBandLabel = (band?: string | null) => {
  if (!band) return "—";
  const map: Record<string, string> = {
    low: "низкий",
    medium: "средний",
    high: "высокий",
    block: "блок",
    review: "проверка",
  };
  return map[band] ?? band;
};

const diffBadgeLabel: Record<string, string> = {
  removed: "убрано",
  weakened: "ослаблено",
  strengthened: "усилено",
  added: "добавлено",
  unchanged: "без изменений",
};

const formatDelta = (delta?: number | null) => {
  if (delta === null || delta === undefined) return "—";
  const sign = delta > 0 ? "+" : "";
  return `${sign}${delta.toFixed(2)}`;
};

const collectEvidenceRefs = (node: ExplainReasonNode): Set<string> => {
  const refs = new Set(node.evidence_refs ?? []);
  (node.children ?? []).forEach((child) => {
    collectEvidenceRefs(child).forEach((ref) => refs.add(ref));
  });
  return refs;
};

const confidenceLabel = (value?: number | null) => {
  if (value === null || value === undefined) return "—";
  if (value >= 0.75) return "High";
  if (value >= 0.4) return "Med";
  return "Low";
};

const renderEvidenceValue = (item: ExplainEvidence) => {
  if (item.value === null || item.value === undefined) return null;
  if (item.type === "metric" && typeof item.value === "object") {
    const actual = (item.value as Record<string, unknown>).actual ?? (item.value as Record<string, unknown>).value;
    const threshold = (item.value as Record<string, unknown>).threshold ?? (item.value as Record<string, unknown>).limit;
    if (actual !== undefined || threshold !== undefined) {
      return (
        <div className="explain-evidence__kv">
          <div>
            <span className="muted small">Actual</span>
            <strong>{String(actual ?? "—")}</strong>
          </div>
          <div>
            <span className="muted small">Threshold</span>
            <strong>{String(threshold ?? "—")}</strong>
          </div>
        </div>
      );
    }
  }
  if (item.type === "field" && typeof item.value === "object") {
    const home = (item.value as Record<string, unknown>).home;
    const station = (item.value as Record<string, unknown>).station;
    if (home !== undefined || station !== undefined) {
      return (
        <div className="explain-evidence__kv">
          <div>
            <span className="muted small">Home</span>
            <strong>{String(home ?? "—")}</strong>
          </div>
          <div>
            <span className="muted small">Station</span>
            <strong>{String(station ?? "—")}</strong>
          </div>
        </div>
      );
    }
  }
  if (typeof item.value === "object") {
    return (
      <details className="explain-evidence__details">
        <summary>Details</summary>
        <pre className="explain-evidence__value">{JSON.stringify(item.value, null, 2)}</pre>
      </details>
    );
  }
  return <pre className="explain-evidence__value">{JSON.stringify(item.value, null, 2)}</pre>;
};

const ReasonTreeNode = ({
  node,
  level,
  expanded,
  selectedId,
  onToggle,
  onSelect,
}: {
  node: ExplainReasonNode;
  level: number;
  expanded: Set<string>;
  selectedId?: string | null;
  onToggle: (id: string) => void;
  onSelect: (node: ExplainReasonNode) => void;
}) => {
  const hasChildren = Boolean(node.children && node.children.length);
  const isExpanded = expanded.has(node.id);
  const children = node.children ? [...node.children].sort((a, b) => b.weight - a.weight) : [];
  const evidenceCount = collectEvidenceRefs(node).size;

  return (
    <div className="explain-tree__node">
      <div className={`explain-tree__row${selectedId === node.id ? " is-selected" : ""}`}>
        <button
          type="button"
          className="explain-tree__toggle"
          onClick={() => onToggle(node.id)}
          disabled={!hasChildren}
        >
          {hasChildren ? (isExpanded ? "−" : "+") : "•"}
        </button>
        <button type="button" className="explain-tree__title" onClick={() => onSelect(node)}>
          <span className="explain-tree__label">
            {node.title}
            {selectedId === node.id ? <span className="explain-tree__selected">selected</span> : null}
          </span>
          <span className="explain-tree__meta">
            {evidenceCount ? <span className="explain-tree__count">{evidenceCount}</span> : null}
            <span className="explain-tree__weight">{percent(node.weight)}</span>
          </span>
        </button>
      </div>
      {hasChildren && isExpanded ? (
        <div className="explain-tree__children" style={{ marginLeft: level * 16 }}>
          {children.map((child) => (
            <ReasonTreeNode
              key={child.id}
              node={child}
              level={level + 1}
              expanded={expanded}
              selectedId={selectedId}
              onToggle={onToggle}
              onSelect={onSelect}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
};

const EvidenceCard = ({ item, highlighted }: { item: ExplainEvidence; highlighted: boolean }) => (
  <div className={`explain-evidence__card${highlighted ? " is-highlighted" : ""}`} data-evidence-id={item.id}>
    <div className="explain-evidence__meta">
      <div className="explain-evidence__chips">
        <span className="pill pill--neutral">{item.type}</span>
        <span className="pill pill--outline">{item.source ?? "unknown"}</span>
        <span className="pill pill--outline">Conf: {confidenceLabel(item.confidence)}</span>
        {highlighted ? <span className="pill pill--accent">связано</span> : null}
      </div>
    </div>
    <div className="explain-evidence__label">{item.label}</div>
    {renderEvidenceValue(item)}
  </div>
);

export function ExplainPage() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const { user } = useAuth();
  const { toast, showToast } = useToast();
  const [payload, setPayload] = useState<ExplainV2Response | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<EvidenceFilter>("all");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [selectedReasonId, setSelectedReasonId] = useState<string | null>(null);
  const [selectedEvidenceIds, setSelectedEvidenceIds] = useState<Set<string>>(new Set());
  const [diffData, setDiffData] = useState<ExplainDiffResponse | null>(null);
  const [diffError, setDiffError] = useState<string | null>(null);
  const [isDiffLoading, setIsDiffLoading] = useState(false);
  const [showDiff, setShowDiff] = useState(false);
  const [leftSnapshot, setLeftSnapshot] = useState("");
  const [rightSnapshot, setRightSnapshot] = useState("");
  const [actionId, setActionId] = useState("");
  const [reasonTab, setReasonTab] = useState<ExplainDiffTab>("strong");

  const kind = searchParams.get("kind") ?? (searchParams.get("kpi_key") ? "kpi" : null);
  const entityId = searchParams.get("id") ?? id ?? null;
  const kpiKey = searchParams.get("kpi_key");
  const windowDays = searchParams.get("window_days") ?? "7";
  const diffRequested = searchParams.get("diff") === "1";

  useEffect(() => {
    if (payload?.reason_tree) {
      setExpanded(new Set([payload.reason_tree.id]));
      setSelectedReasonId(null);
      setSelectedEvidenceIds(new Set());
      setFilter("all");
    }
  }, [payload?.reason_tree]);

  useEffect(() => {
    setDiffData(null);
    setDiffError(null);
    setShowDiff(false);
  }, [payload?.id, kind]);

  useEffect(() => {
    setReasonTab("strong");
  }, [diffData]);
  useEffect(() => {
    setLeftSnapshot(searchParams.get("left_snapshot") ?? "");
    setRightSnapshot(searchParams.get("right_snapshot") ?? "");
    setActionId(searchParams.get("action_id") ?? "");
    if (diffRequested) {
      setShowDiff(true);
    }
  }, [diffRequested, searchParams]);

  useEffect(() => {
    if (selectedReasonId) {
      setFilter("linked");
    } else {
      setFilter("all");
    }
  }, [selectedReasonId]);

  const linkedEvidenceIds = useMemo(() => selectedEvidenceIds, [selectedEvidenceIds]);

  const evidence = useMemo(() => {
    const items = payload?.evidence ?? [];
    if (filter === "linked" && linkedEvidenceIds.size > 0) {
      return items.filter((item) => linkedEvidenceIds.has(item.id));
    }
    return items;
  }, [filter, linkedEvidenceIds, payload?.evidence]);

  const toggle = useCallback((nodeId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  }, []);

  const loadExplain = useCallback(async () => {
    if (!user) return;
    if (!kind) {
      setError("Не указан тип explain.");
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {};
      if (kind === "kpi") {
        if (!kpiKey) {
          setError("Не указан KPI.");
          setIsLoading(false);
          return;
        }
        params.kpi_key = kpiKey;
        params.window_days = windowDays;
      } else if (entityId) {
        params.kind = kind;
        params.id = entityId;
      } else {
        setError("Не указан идентификатор.");
        setIsLoading(false);
        return;
      }
      const data = await fetchExplainV2(user, params);
      setPayload(data);
      if (data.reason_tree) {
        setExpanded(new Set([data.reason_tree.id]));
      }
    } catch (err) {
      setError((err as Error).message);
      setPayload(null);
    } finally {
      setIsLoading(false);
    }
  }, [entityId, kind, kpiKey, user, windowDays]);

  useEffect(() => {
    void loadExplain();
  }, [loadExplain]);

  const copyLink = useCallback(() => {
    const url = window.location.href;
    void navigator.clipboard.writeText(url);
    showToast("success", "Ссылка скопирована");
  }, [showToast]);

  const actionOptions = useMemo(
    () =>
      payload?.recommended_actions.map((item) => ({
        action_code: item.action_code,
        label: item.title,
        description: item.description ?? null,
        recommended: true,
      })) ?? [],
    [payload?.recommended_actions],
  );

  const handleSelectNode = useCallback((node: ExplainReasonNode) => {
    setSelectedReasonId((prev) => {
      if (prev === node.id) {
        setSelectedEvidenceIds(new Set());
        return null;
      }
      setSelectedEvidenceIds(collectEvidenceRefs(node));
      return node.id;
    });
  }, []);

  const loadDiff = useCallback(async () => {
    if (!user || !kind) return;
    if (!leftSnapshot || !rightSnapshot) {
      setDiffError("Укажите snapshot для сравнения.");
      setShowDiff(true);
      return;
    }
    setIsDiffLoading(true);
    setDiffError(null);
    try {
      const diffKind = (kind === "marketplace_order" ? "order" : kind) as "operation" | "invoice" | "order" | "kpi";
      const response = await fetchExplainDiff(user, {
        kind: diffKind,
        id: diffKind === "kpi" ? undefined : entityId ?? undefined,
        left_snapshot: leftSnapshot,
        right_snapshot: rightSnapshot,
        action_id: actionId || undefined,
      });
      setDiffData(response);
      setShowDiff(true);
    } catch (err) {
      setDiffError((err as Error).message);
      setDiffData(null);
      setShowDiff(true);
    } finally {
      setIsDiffLoading(false);
    }
  }, [actionId, entityId, kind, leftSnapshot, rightSnapshot, user]);

  const reasonSummary = useMemo(
    () => reduceExplainDiffReasons(diffData?.reasons_diff ?? [], reasonTab),
    [diffData?.reasons_diff, reasonTab],
  );

  const snapshotOptions = useMemo(() => {
    const options: { value: string; label: string }[] = [
      {
        value: "latest",
        label: payload?.generated_at ? `Последний · ${formatTimestamp(payload.generated_at)}` : "Последний",
      },
      { value: "previous", label: "Предыдущий" },
      { value: "baseline", label: "Baseline" },
    ];
    if (payload?.policy_snapshot) {
      options.push({ value: payload.policy_snapshot, label: `Policy · ${payload.policy_snapshot}` });
    }
    if (payload?.generated_at) {
      options.push({
        value: `generated_at:${payload.generated_at}`,
        label: `Generated · ${formatTimestamp(payload.generated_at)}`,
      });
    }
    const ensureOption = (value: string) => {
      if (!value) return;
      if (!options.some((item) => item.value === value)) {
        options.push({ value, label: `Выбран: ${value}` });
      }
    };
    ensureOption(leftSnapshot);
    ensureOption(rightSnapshot);
    return options;
  }, [leftSnapshot, payload?.generated_at, payload?.policy_snapshot, rightSnapshot]);

  if (showDiff) {
    return (
      <div className="card">
        <div className="card__header">
          <Toast toast={toast} />
          <div>
            <h2>Explain Diff</h2>
            <p className="muted">До → После · режим сравнения</p>
          </div>
          <button type="button" className="ghost" onClick={() => setShowDiff(false)}>
            Назад к explain
          </button>
        </div>

        <div className="explain-diff__controls">
          <label>
            Снимок: До
            <select value={leftSnapshot} onChange={(event) => setLeftSnapshot(event.target.value)}>
              <option value="">Выберите...</option>
              {snapshotOptions.map((option) => (
                <option key={`left-${option.value}`} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <input
              type="text"
              value={leftSnapshot}
              onChange={(event) => setLeftSnapshot(event.target.value)}
              placeholder="snapshot_id / policy_version"
            />
          </label>
          <label>
            Снимок: После
            <select value={rightSnapshot} onChange={(event) => setRightSnapshot(event.target.value)}>
              <option value="">Выберите...</option>
              {snapshotOptions.map((option) => (
                <option key={`right-${option.value}`} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <input
              type="text"
              value={rightSnapshot}
              onChange={(event) => setRightSnapshot(event.target.value)}
              placeholder="snapshot_id / policy_version"
            />
          </label>
          <label>
            Action (optional)
            <input
              type="text"
              value={actionId}
              onChange={(event) => setActionId(event.target.value)}
              placeholder="action_id"
            />
          </label>
          <div className="explain-diff__controls-actions">
            <button type="button" className="primary" onClick={() => void loadDiff()}>
              Сравнить
            </button>
            <button type="button" className="ghost" disabled title="Экспорт скоро">
              Экспорт
            </button>
          </div>
        </div>

        {isDiffLoading ? <AppLoadingState label="Готовим diff..." /> : null}
        {diffError ? (
          <AppErrorState message={diffError} onRetry={loadDiff} />
        ) : null}

        {diffData ? (
          <div className="explain-diff__panel">
            <div className="explain-diff__meta">
              <div className="explain-diff__meta-item">
                <span className="muted small">{diffData.meta.left.label}</span>
                <strong>{diffData.decision_diff.before ?? "—"}</strong>
              </div>
              <div className="explain-diff__meta-item">
                <span className="muted small">→</span>
              </div>
              <div className="explain-diff__meta-item">
                <span className="muted small">{diffData.meta.right.label}</span>
                <strong>{diffData.decision_diff.after ?? "—"}</strong>
              </div>
              <div className="explain-diff__meta-item">
                <span className="muted small">Δ риска</span>
                <strong
                  className={`explain-diff__delta ${diffData.score_diff.delta && diffData.score_diff.delta < 0 ? "is-improved" : diffData.score_diff.delta && diffData.score_diff.delta > 0 ? "is-worsened" : ""}`}
                >
                  {diffData.score_diff.delta === null || diffData.score_diff.delta === undefined
                    ? "—"
                    : `${diffData.score_diff.delta < 0 ? "↓" : diffData.score_diff.delta > 0 ? "↑" : "→"} ${formatDelta(
                        diffData.score_diff.delta,
                      )}`}
                </strong>
              </div>
            </div>

            <div className="card explain-card explain-diff__summary">
              <div>
                <div className="muted small">Risk</div>
                <div className="explain-diff__risk">
                  <strong>{diffData.score_diff.risk_before?.toFixed(2) ?? "—"}</strong>
                  <span>→</span>
                  <strong>{diffData.score_diff.risk_after?.toFixed(2) ?? "—"}</strong>
                </div>
              </div>
              <div
                className={`explain-diff__delta ${diffData.score_diff.delta && diffData.score_diff.delta < 0 ? "is-improved" : diffData.score_diff.delta && diffData.score_diff.delta > 0 ? "is-worsened" : ""}`}
              >
                {formatDelta(diffData.score_diff.delta)}
              </div>
            </div>

            <div className="card explain-card">
              <div className="explain-diff__section-header">
                <h3>Причины</h3>
              </div>
              <div className="explain-diff__tabs">
                {(
                  [
                    { id: "strong", label: "Сильно изменилось" },
                    { id: "added", label: "Добавилось" },
                    { id: "removed", label: "Убрано" },
                    { id: "all", label: "Показать всё" },
                  ] as const
                ).map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    className={`explain-diff__tab${reasonTab === tab.id ? " is-active" : ""}`}
                    onClick={() => setReasonTab(tab.id)}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
              <div className="explain-diff__table">
                <div className="explain-diff__row explain-diff__row--head">
                  <span>Причина</span>
                  <span>Было</span>
                  <span>Стало</span>
                  <span>Δ</span>
                </div>
                {reasonSummary.visible.length ? (
                  reasonSummary.visible.map((reason) => (
                    <div key={reason.reason_code} className={`explain-diff__row is-${reason.status}`}>
                      <span className="explain-diff__reason">
                        {reason.reason_code}
                        <span className="pill pill--outline">{diffBadgeLabel[reason.status]}</span>
                      </span>
                      <span>{reason.weight_before ?? "—"}</span>
                      <span>{reason.weight_after ?? "—"}</span>
                      <span>{formatDelta(reason.delta)}</span>
                    </div>
                  ))
                ) : (
                  <div className="muted small">Нет значимых изменений.</div>
                )}
              </div>
            </div>

            <div className="card explain-card">
              <h3>Evidence</h3>
              {diffData.evidence_diff.length ? (
                <div className="explain-diff__evidence-columns">
                  {(["removed", "added"] as const).map((status) => (
                    <div key={status} className="explain-diff__evidence-column">
                      <div className="muted small">{status === "removed" ? "Removed" : "Added"}</div>
                      <div className="explain-diff__list">
                        {diffData.evidence_diff
                          .filter((item) => item.status === status)
                          .map((item) => (
                            <button
                              key={item.evidence_id}
                              type="button"
                              className={`explain-diff__item is-${item.status}`}
                              onClick={() => {
                                const anchor = document.querySelector(`[data-evidence-id="${item.evidence_id}"]`);
                                if (anchor) {
                                  anchor.scrollIntoView({ behavior: "smooth", block: "center" });
                                }
                              }}
                            >
                              <span>{item.evidence_id}</span>
                              <span className="pill pill--outline">{item.status}</span>
                            </button>
                          ))}
                        {!diffData.evidence_diff.some((item) => item.status === status) ? (
                          <div className="muted small">Нет изменений.</div>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="muted small">Изменений нет.</div>
              )}
            </div>

            {diffData.action_impact ? (
              <div className="card explain-card">
                <h3>Action impact</h3>
                <div className="explain-diff__action">
                  <div>
                    <div className="muted small">Action</div>
                    <strong>{diffData.action_impact.action_id}</strong>
                  </div>
                  <div>
                    <div className="muted small">Ожидаемый эффект</div>
                    <strong>{formatDelta(diffData.action_impact.expected_delta)}</strong>
                  </div>
                  <div>
                    <div className="muted small">Confidence</div>
                    <strong>{diffData.action_impact.confidence.toFixed(2)}</strong>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card__header">
        <Toast toast={toast} />
        <div>
          <h2>Explain v2</h2>
          <p className="muted">Почему принято решение и какие есть доказательства.</p>
        </div>
        <div className="stack-inline">
          <button
            type="button"
            className="ghost"
            onClick={() => setShowDiff(true)}
          >
            Сравнить
          </button>
          <button type="button" className="ghost" onClick={copyLink}>
            Скопировать ссылку
          </button>
          <button type="button" className="ghost" title="В разработке" disabled>
            Экспорт
          </button>
          <Link className="ghost" to="/dashboard">
            На дашборд
          </Link>
        </div>
      </div>

      {isLoading ? <AppLoadingState label="Загружаем explain..." /> : null}
      {error ? <AppErrorState message={error} onRetry={loadExplain} /> : null}

      {!isLoading && !error && !payload?.reason_tree ? (
        <AppEmptyState title="Explain недоступен" description="Попробуйте позже или уточните параметры." />
      ) : null}

      {payload ? (
        <div className="stack">
          <section className="card__section">
            <div className="explain-header">
              <div>
                <span
                  className={`pill pill--${payload.decision === "DECLINE" ? "danger" : payload.decision === "APPROVE" ? "success" : "neutral"}`}
                >
                  {payload.decision}
                </span>
                <div className="muted small">
                  Score: {payload.score ?? "—"} • Band: {scoreBandLabel(payload.score_band)}
                </div>
              </div>
              <div className="muted small">
                {payload.policy_snapshot ? `Policy: ${payload.policy_snapshot}` : "Policy: —"}
                <div>{formatTimestamp(payload.generated_at)}</div>
              </div>
            </div>
          </section>

          <section className="card__section">
            <h3>Reason Tree</h3>
            {payload.reason_tree ? (
              <div className="explain-tree">
                <ReasonTreeNode
                  node={payload.reason_tree}
                  level={1}
                  expanded={expanded}
                  selectedId={selectedReasonId}
                  onToggle={toggle}
                  onSelect={handleSelectNode}
                />
              </div>
            ) : (
              <p className="muted">Reason tree недоступен.</p>
            )}
          </section>

          <section className="card__section">
            <div className="stack-inline" style={{ justifyContent: "space-between" }}>
              <h3>Evidence</h3>
              <div className="explain-filter">
                <label>
                  <input type="radio" checked={filter === "all"} onChange={() => setFilter("all")} /> Все
                </label>
                <label>
                  <input
                    type="radio"
                    checked={filter === "linked"}
                    onChange={() => setFilter("linked")}
                    disabled={linkedEvidenceIds.size === 0}
                  />{" "}
                  Связанные
                </label>
              </div>
            </div>
            <div className="explain-evidence">
              {filter === "linked" && selectedReasonId && evidence.length === 0 ? (
                <p className="muted">Нет доказательств для выбранной причины.</p>
              ) : evidence.length ? (
                evidence.map((item) => (
                  <EvidenceCard key={item.id} item={item} highlighted={linkedEvidenceIds.has(item.id)} />
                ))
              ) : (
                <p className="muted">Evidence отсутствуют.</p>
              )}
            </div>
          </section>

          <section className="card__section">
            <h3>Documents</h3>
            {payload.documents.length ? (
              <div className="explain-docs">
                {payload.documents.map((doc) => (
                  <a key={doc.id} href={doc.url} target="_blank" rel="noreferrer">
                    {doc.title}
                  </a>
                ))}
              </div>
            ) : (
              <AppEmptyState title="Документы отсутствуют" description="Нет связанных документов." />
            )}
          </section>

          <section className="card__section">
            <h3>Recommended actions</h3>
            <div className="explain-actions">
              {actionOptions.length ? (
                actionOptions.map((action) => (
                  <div key={action.action_code} className="explain-action">
                    <div className="explain-action__body">
                      <div className="explain-action__title">
                        {action.label}
                        {action.recommended ? <span className="pill pill--accent">recommended</span> : null}
                      </div>
                      {action.description ? <div className="muted small">{action.description}</div> : null}
                    </div>
                  </div>
                ))
              ) : (
                <p className="muted">Рекомендации отсутствуют.</p>
              )}
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}
