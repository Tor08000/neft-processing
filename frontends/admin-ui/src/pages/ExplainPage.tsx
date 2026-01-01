import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Toast } from "../components/common/Toast";
import { useToast } from "../components/Toast/useToast";
import { fetchExplainActions, fetchExplainDiff, fetchExplainV2, evaluateWhatIf } from "../api/explainV2";
import type {
  ExplainActionCatalogItem,
  ExplainDiffResponse,
  ExplainEvidence,
  ExplainReasonNode,
  ExplainV2Response,
  WhatIfResponse,
} from "../types/explainV2";

type EvidenceFilter = "all" | "linked";
type ExplainActionOption = ExplainActionCatalogItem & { recommended?: boolean };

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

const diffBadgeLabel: Record<string, string> = {
  removed: "устранено",
  weakened: "ослаблено",
  strengthened: "усилено",
  added: "добавлено",
};

const riskDeltaLabel = (delta: number) => {
  const percentValue = Math.abs(delta * 100).toFixed(0);
  if (delta < 0) return `Риск снизится на ${percentValue}%`;
  if (delta > 0) return `Риск вырастет на ${percentValue}%`;
  return "Риск не изменится";
};

const buildReasonStatusMap = (diff: ExplainDiffResponse | null) => {
  const map = new Map<string, string>();
  if (!diff) return map;
  diff.diff.reasons.removed.forEach((code) => map.set(code, "removed"));
  diff.diff.reasons.added.forEach((code) => map.set(code, "added"));
  diff.diff.reasons.weakened.forEach((item) => map.set(item.code, "weakened"));
  diff.diff.reasons.strengthened.forEach((item) => map.set(item.code, "strengthened"));
  return map;
};

const buildEvidenceStatusMap = (diff: ExplainDiffResponse | null) => {
  const map = new Map<string, string>();
  if (!diff) return map;
  diff.diff.evidence.removed.forEach((id) => map.set(id, "removed"));
  diff.diff.evidence.added.forEach((id) => map.set(id, "added"));
  return map;
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
  <div className={`explain-evidence__card${highlighted ? " is-highlighted" : ""}`}>
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

export const ExplainPage = () => {
  const [searchParams] = useSearchParams();
  const { toast, showToast } = useToast();
  const [payload, setPayload] = useState<ExplainV2Response | null>(null);
  const [actionsCatalog, setActionsCatalog] = useState<ExplainActionCatalogItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<EvidenceFilter>("all");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedActions, setSelectedActions] = useState<ExplainActionCatalogItem[]>([]);
  const [whatIf, setWhatIf] = useState<WhatIfResponse | null>(null);
  const [whatIfError, setWhatIfError] = useState<string | null>(null);
  const [isWhatIfLoading, setIsWhatIfLoading] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [selectedReasonId, setSelectedReasonId] = useState<string | null>(null);
  const [selectedEvidenceIds, setSelectedEvidenceIds] = useState<Set<string>>(new Set());
  const [diffData, setDiffData] = useState<ExplainDiffResponse | null>(null);
  const [diffError, setDiffError] = useState<string | null>(null);
  const [isDiffLoading, setIsDiffLoading] = useState(false);
  const [showDiff, setShowDiff] = useState(false);
  const [hoveredReason, setHoveredReason] = useState<string | null>(null);
  const beforeRef = useRef<HTMLDivElement | null>(null);
  const afterRef = useRef<HTMLDivElement | null>(null);
  const syncGuard = useRef(false);

  const kind = searchParams.get("kind") ?? (searchParams.get("kpi_key") ? "kpi" : null);
  const entityId = searchParams.get("id");
  const kpiKey = searchParams.get("kpi_key");
  const windowDays = searchParams.get("window_days") ?? "7";

  useEffect(() => {
    if (payload?.reason_tree) {
      setExpanded(new Set([payload.reason_tree.id]));
      setSelectedReasonId(null);
      setSelectedEvidenceIds(new Set());
      setFilter("all");
    }
  }, [payload?.reason_tree]);

  useEffect(() => {
    setSelectedActions([]);
  }, [payload?.id]);

  useEffect(() => {
    setDiffData(null);
    setDiffError(null);
    setShowDiff(false);
  }, [payload?.id, kind]);

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

  const loadExplain = useCallback(async () => {
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
      const data = await fetchExplainV2(params);
      setPayload(data);
    } catch (err) {
      setError((err as Error).message);
      setPayload(null);
    } finally {
      setIsLoading(false);
    }
  }, [entityId, kind, kpiKey, windowDays]);

  const loadActions = useCallback(async () => {
    if (!kind) return;
    try {
      const params: Record<string, string> = {};
      if (kind === "kpi") {
        if (!kpiKey) return;
        params.kpi_key = kpiKey;
      } else if (entityId) {
        params.kind = kind;
        params.id = entityId;
      } else {
        return;
      }
      const data = await fetchExplainActions(params);
      setActionsCatalog(data);
    } catch {
      setActionsCatalog([]);
    }
  }, [entityId, kind, kpiKey]);

  useEffect(() => {
    void loadExplain();
    void loadActions();
  }, [loadExplain, loadActions]);

  const copyLink = useCallback(() => {
    const url = window.location.href;
    void navigator.clipboard.writeText(url);
    showToast("success", "Ссылка скопирована");
  }, [showToast]);

  const toggleNode = useCallback((nodeId: string) => {
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
    if (!kind || selectedActions.length < 1) return;
    const targetId = kind === "kpi" ? kpiKey : entityId;
    if (!targetId) return;
    setIsDiffLoading(true);
    setDiffError(null);
    try {
      const diffKind = (kind === "marketplace_order" ? "order" : kind) as "operation" | "invoice" | "order" | "kpi";
      const response = await fetchExplainDiff({
        context: { kind: diffKind, id: targetId },
        actions: selectedActions.map((item) => ({ code: item.action_code })),
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
  }, [entityId, kind, kpiKey, selectedActions]);

  const actionOptions = useMemo<ExplainActionOption[]>(() => {
    const merged = [
      ...(payload?.recommended_actions.map((item) => ({
        action_code: item.action_code,
        label: item.title,
        description: item.description ?? null,
        recommended: true,
      })) ?? []),
      ...actionsCatalog.map((item) => ({ ...item, recommended: false })),
    ];
    const seen = new Map<string, ExplainActionOption>();
    merged.forEach((item) => {
      if (!seen.has(item.action_code)) {
        seen.set(item.action_code, item);
      }
    });
    return Array.from(seen.values());
  }, [actionsCatalog, payload?.recommended_actions]);

  const selectedActionCodes = useMemo(() => new Set(selectedActions.map((item) => item.action_code)), [selectedActions]);

  const toggleAction = useCallback(
    (item: ExplainActionCatalogItem) => {
      setSelectedActions((prev) => {
        const exists = prev.find((action) => action.action_code === item.action_code);
        if (exists) {
          return prev.filter((action) => action.action_code !== item.action_code);
        }
        if (prev.length >= 3) return prev;
        return [...prev, item];
      });
    },
    [],
  );

  const openWhatIf = useCallback(() => {
    setDrawerOpen(true);
    setWhatIf(null);
    setWhatIfError(null);
  }, []);

  const evaluate = useCallback(async () => {
    if (!kind || !entityId) return;
    const subjectType = kind === "operation" ? "FUEL_TX" : kind === "invoice" ? "INVOICE" : "ORDER";
    setIsWhatIfLoading(true);
    setWhatIfError(null);
    try {
      const response = await evaluateWhatIf({
        subject: { type: subjectType, id: entityId },
        max_candidates: Math.min(3, Math.max(1, selectedActions.length)),
      });
      setWhatIf(response);
    } catch (err) {
      setWhatIfError((err as Error).message);
      setWhatIf(null);
    } finally {
      setIsWhatIfLoading(false);
    }
  }, [entityId, kind, selectedActions.length]);

  const candidatesByAction = useMemo(() => {
    if (!whatIf) return new Map<string, WhatIfResponse["candidates"][number]>();
    return new Map(whatIf.candidates.map((candidate) => [candidate.action.code, candidate]));
  }, [whatIf]);

  const filteredCandidates = useMemo(() => {
    if (!selectedActions.length) return [];
    return selectedActions.map((action) => ({
      action,
      candidate: candidatesByAction.get(action.action_code) ?? null,
    }));
  }, [candidatesByAction, selectedActions]);

  const canCompare = kind !== "kpi" && entityId;
  const canDiff = Boolean(kind === "kpi" ? kpiKey : entityId);

  const reasonStatusMap = useMemo(() => buildReasonStatusMap(diffData), [diffData]);
  const evidenceStatusMap = useMemo(() => buildEvidenceStatusMap(diffData), [diffData]);

  const handleScrollSync = useCallback((source: "before" | "after") => {
    if (syncGuard.current) return;
    const sourceEl = source === "before" ? beforeRef.current : afterRef.current;
    const targetEl = source === "before" ? afterRef.current : beforeRef.current;
    if (!sourceEl || !targetEl) return;
    syncGuard.current = true;
    targetEl.scrollTop = sourceEl.scrollTop;
    window.setTimeout(() => {
      syncGuard.current = false;
    }, 0);
  }, []);

  useEffect(() => {
    if (drawerOpen && canCompare && selectedActions.length >= 2 && !isWhatIfLoading) {
      void evaluate();
    }
  }, [drawerOpen, canCompare, selectedActions.length, evaluate, isWhatIfLoading]);

  return (
    <div className="explain-v2">
      <Toast toast={toast} />
      <div className="page-header">
        <div>
          <h1>Explain v2</h1>
          <p className="muted">Почему принято решение и как можно повлиять на риск.</p>
        </div>
        <div className="stack-inline">
          <button
            type="button"
            className="neft-btn-secondary"
            onClick={() => void loadDiff()}
            disabled={selectedActions.length < 1 || !canDiff}
          >
            Показать изменения
          </button>
          <button type="button" className="neft-btn-secondary" onClick={copyLink}>
            Скопировать ссылку
          </button>
          <button type="button" className="neft-btn-secondary" title="В разработке" disabled>
            Экспорт
          </button>
        </div>
      </div>

      {isLoading ? <div className="card">Загружаем explain...</div> : null}
      {error ? (
        <div className="card card--error">
          <div>Ошибка: {error}</div>
          <button type="button" className="ghost" onClick={() => void loadExplain()}>
            Повторить
          </button>
        </div>
      ) : null}

      {!isLoading && !error && !payload?.reason_tree ? (
        <div className="card card--empty">Explain недоступен. Попробуйте позже.</div>
      ) : null}

      {payload ? (
        <div className="explain-grid">
          <section className="card explain-card">
            <div className="explain-header">
              <div>
                <div className={`pill pill--${payload.decision === "DECLINE" ? "danger" : payload.decision === "APPROVE" ? "success" : "neutral"}`}>
                  {payload.decision}
                </div>
                <div className="explain-header__meta">
                  <span>Score: {payload.score ?? "—"}</span>
                  <span>Band: {scoreBandLabel(payload.score_band)}</span>
                </div>
              </div>
              <div className="explain-header__meta">
                <span>Policy: {payload.policy_snapshot ?? "—"}</span>
                <span>{formatTimestamp(payload.generated_at)}</span>
              </div>
            </div>
          </section>

          <section className="card explain-card">
            <div className="card__header">
              <h3>Reason Tree</h3>
            </div>
            {payload.reason_tree ? (
              <div className="explain-tree">
                <ReasonTreeNode
                  node={payload.reason_tree}
                  level={1}
                  expanded={expanded}
                  selectedId={selectedReasonId}
                  onToggle={toggleNode}
                  onSelect={handleSelectNode}
                />
              </div>
            ) : (
              <div className="muted">Reason tree недоступен.</div>
            )}
          </section>

          <section className="card explain-card">
            <div className="card__header">
              <h3>Evidence</h3>
              <div className="explain-filter">
                <label>
                  <input
                    type="radio"
                    checked={filter === "all"}
                    onChange={() => setFilter("all")}
                  />
                  Все
                </label>
                <label>
                  <input
                    type="radio"
                    checked={filter === "linked"}
                    onChange={() => setFilter("linked")}
                    disabled={linkedEvidenceIds.size === 0}
                  />
                  Связанные
                </label>
              </div>
            </div>
            <div className="explain-evidence">
              {filter === "linked" && selectedReasonId && evidence.length === 0 ? (
                <div className="muted">Нет доказательств для выбранной причины.</div>
              ) : evidence.length ? (
                evidence.map((item) => (
                  <EvidenceCard key={item.id} item={item} highlighted={linkedEvidenceIds.has(item.id)} />
                ))
              ) : (
                <div className="muted">Evidence отсутствуют.</div>
              )}
            </div>
          </section>

          <section className="card explain-card">
            <div className="card__header">
              <h3>Documents</h3>
            </div>
            {payload.documents.length ? (
              <div className="explain-docs">
                {payload.documents.map((doc) => (
                  <a key={doc.id} href={doc.url} target="_blank" rel="noreferrer" className="ghost">
                    {doc.title}
                  </a>
                ))}
              </div>
            ) : (
              <div className="card card--empty">Документы отсутствуют.</div>
            )}
          </section>

          <section className="card explain-card">
            <div className="card__header">
              <h3>Recommended actions</h3>
            </div>
            <div className="explain-actions">
              {actionOptions.length ? (
                actionOptions.map((action) => {
                  const disabled = !selectedActionCodes.has(action.action_code) && selectedActions.length >= 3;
                  return (
                    <label
                      key={action.action_code}
                      className={`explain-action${disabled ? " is-disabled" : ""}`}
                      title={disabled ? "Максимум 3" : undefined}
                    >
                      <input
                        type="checkbox"
                        checked={selectedActionCodes.has(action.action_code)}
                        onChange={() => toggleAction(action)}
                        disabled={disabled}
                      />
                      <div className="explain-action__body">
                        <div className="explain-action__title">
                          {action.label}
                          {action.recommended ? <span className="pill pill--accent">recommended</span> : null}
                        </div>
                        {action.description ? <div className="muted small">{action.description}</div> : null}
                        {action.risk_hint ? <div className="muted small">Hint: {action.risk_hint}</div> : null}
                      </div>
                    </label>
                  );
                })
              ) : (
                <div className="muted">Рекомендации отсутствуют.</div>
              )}
            </div>
            <div className="explain-actions__footer">
              <button
                type="button"
                className="primary"
                onClick={() => void loadDiff()}
                disabled={!canDiff || selectedActions.length < 1}
              >
                Показать изменения
              </button>
              {!canCompare ? <span className="muted small">What-if доступен только для операций/инвойсов/заказов.</span> : null}
              {selectedActions.length < 1 ? <span className="muted small">Выберите минимум 1 действие.</span> : null}
              <button type="button" className="ghost" onClick={openWhatIf} disabled={!canCompare}>
                Открыть What-if
              </button>
            </div>
          </section>
        </div>
      ) : null}

      {drawerOpen ? (
        <div className="explain-drawer">
          <div className="explain-drawer__content">
            <div className="explain-drawer__header">
              <h3>What-if сравнение</h3>
              <button type="button" className="ghost" onClick={() => setDrawerOpen(false)}>
                Закрыть
              </button>
            </div>
            <div className="explain-drawer__body">
              <div className="explain-drawer__actions">
                <h4>Выбранные действия</h4>
                <div className="explain-drawer__list">
                  {selectedActions.length ? (
                    selectedActions.map((item) => (
                      <div key={item.action_code} className="explain-drawer__selected">
                        <strong>{item.label}</strong>
                        {item.description ? <span className="muted small">{item.description}</span> : null}
                      </div>
                    ))
                  ) : (
                    <div className="muted small">Выберите 2–3 действия в списке выше.</div>
                  )}
                </div>
                <button
                  type="button"
                  className="primary"
                  onClick={() => void evaluate()}
                  disabled={!canCompare || selectedActions.length < 2 || isWhatIfLoading}
                >
                  Запустить симуляцию
                </button>
                <button type="button" className="ghost" onClick={() => void loadDiff()} disabled={selectedActions.length < 1}>
                  Показать изменения
                </button>
                <div className="muted small">Применение недоступно — только симуляция.</div>
              </div>

              <div className="explain-drawer__results">
                <div className="explain-whatif-banner">Симуляция (не исполняется)</div>
                {isWhatIfLoading ? <div className="muted">Рассчитываем...</div> : null}
                {whatIfError ? <div className="muted">Ошибка: {whatIfError}</div> : null}
                {filteredCandidates.map(({ action, candidate }) => (
                  <div key={action.action_code} className="explain-whatif-card">
                    <div className="explain-whatif-card__title">{action.label}</div>
                    {candidate ? (
                      <>
                        <div className="explain-whatif-card__meta">
                          <span>Эффект: {candidate.projection.expected_effect_label}</span>
                          <span>Вероятность: {candidate.projection.probability_improved_pct}%</span>
                        </div>
                        <div className="explain-whatif-card__meta">
                          <span>Risk: {candidate.risk.outlook}</span>
                          <span>Memory penalty: {candidate.memory.memory_penalty_pct}%</span>
                        </div>
                      </>
                    ) : (
                      <div className="muted">Нет данных симуляции.</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
};

export default ExplainPage;
