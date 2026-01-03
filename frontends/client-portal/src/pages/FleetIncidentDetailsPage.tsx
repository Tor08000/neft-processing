import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import { AppEmptyState, AppErrorState, AppForbiddenState } from "../components/states";
import { FleetUnavailableState } from "../components/FleetUnavailableState";
import { ConfirmActionModal } from "../components/ConfirmActionModal";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";
import { ApiError } from "../api/http";
import { closeFleetCase, getFleetCase, startFleetCase } from "../api/fleetCases";
import type { FleetCaseDetails, FleetCaseTimelineEvent } from "../types/fleetCases";
import { formatDateTime } from "../utils/format";
import { canCloseFleetIncidents, canStartFleetIncidents, canViewFleetIncidents } from "../utils/fleetPermissions";
import {
  getFleetCasePolicyActionBadgeClass,
  getFleetCaseSeverityBadgeClass,
  getFleetCaseStatusBadgeClass,
  getFleetCaseTriggerBadgeClass,
} from "../utils/fleetCases";

const resolveTimelineTimestamp = (event: FleetCaseTimelineEvent) => event.timestamp ?? event.occurred_at ?? "";

const resolveScopeLink = (details: FleetCaseDetails) => {
  if (details.scope?.card_id) return `/fleet/cards/${details.scope.card_id}`;
  if (details.scope?.group_id) return `/fleet/groups/${details.scope.group_id}`;
  return null;
};

export function FleetIncidentDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const { t } = useI18n();
  const { toast, showToast } = useToast();
  const [details, setDetails] = useState<FleetCaseDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isForbidden, setIsForbidden] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [startOpen, setStartOpen] = useState(false);
  const [closeOpen, setCloseOpen] = useState(false);
  const [startNote, setStartNote] = useState("");
  const [closeSummary, setCloseSummary] = useState("");
  const [closeActions, setCloseActions] = useState("");
  const [unblockedCard, setUnblockedCard] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const canView = canViewFleetIncidents(user);
  const canStart = canStartFleetIncidents(user);
  const canClose = canCloseFleetIncidents(user);

  const loadDetails = useCallback(async () => {
    if (!id || !user?.token) return;
    setLoading(true);
    setError(null);
    setIsForbidden(false);
    setUnavailable(false);
    try {
      const response = await getFleetCase(user.token, id);
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      if (!response.item) {
        setDetails(null);
        return;
      }
      setDetails(response.item);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setIsForbidden(true);
        return;
      }
      setError(err instanceof Error ? err.message : t("fleetIncidents.errors.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [id, t, user?.token]);

  useEffect(() => {
    if (!canView) return;
    void loadDetails();
  }, [canView, loadDetails]);

  const scopeLink = useMemo(() => (details ? resolveScopeLink(details) : null), [details]);

  const scopeLabel = useMemo(() => {
    if (!details) return "—";
    if (details.scope?.card_alias) return details.scope.card_alias;
    if (details.scope?.group_name) return details.scope.group_name;
    return t("fleetIncidents.scope.client");
  }, [details, t]);

  const policyAction = details?.policy_action ?? details?.explain?.policy_action;
  const trigger = details?.source?.type ?? details?.explain?.trigger;

  const showStartButton = details?.status === "OPEN" && canStart;
  const showCloseButton = details?.status === "IN_PROGRESS" && canClose;
  const unblockedReasonLabel = t("fleetIncidents.close.unblockedReason");

  const buildReason = useCallback(
    (resolution: string, actionsTaken: string, unblocked: boolean) => {
      const details = [actionsTaken.trim(), unblocked ? unblockedReasonLabel : ""].filter(Boolean).join(". ");
      if (!details) return resolution.trim();
      return details;
    },
    [unblockedReasonLabel],
  );

  const handleStart = useCallback(async () => {
    if (!id || !user?.token) return;
    setIsSubmitting(true);
    setValidationError(null);
    try {
      const note = startNote.trim() || t("fleetIncidents.start.defaultNote");
      const response = await startFleetCase(user.token, id, note);
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      if (response.item) {
        setDetails(response.item);
      } else {
        setDetails((prev) =>
          prev
            ? {
                ...prev,
                status: "IN_PROGRESS",
                last_updated_at: new Date().toISOString(),
              }
            : prev,
        );
      }
      showToast({ kind: "success", text: t("fleetIncidents.start.toast") });
      setStartOpen(false);
      setStartNote("");
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        showToast({ kind: "error", text: t("fleetIncidents.errors.noPermission") });
        return;
      }
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleetIncidents.errors.actionFailed") });
    } finally {
      setIsSubmitting(false);
    }
  }, [id, showToast, startNote, t, user?.token]);

  const handleClose = useCallback(async () => {
    if (!id || !user?.token) return;
    const trimmedSummary = closeSummary.trim();
    if (!trimmedSummary) {
      setValidationError(t("fleetIncidents.close.validation"));
      return;
    }
    setIsSubmitting(true);
    setValidationError(null);
    try {
      const reason = buildReason(trimmedSummary, closeActions, unblockedCard);
      const response = await closeFleetCase(user.token, id, { reason, resolution: trimmedSummary });
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      if (response.item) {
        setDetails(response.item);
      } else {
        setDetails((prev) =>
          prev
            ? {
                ...prev,
                status: "CLOSED",
                last_updated_at: new Date().toISOString(),
                resolution: {
                  summary: trimmedSummary,
                  reason,
                  actions_taken: closeActions.trim() || null,
                  closed_at: new Date().toISOString(),
                },
              }
            : prev,
        );
      }
      showToast({ kind: "success", text: t("fleetIncidents.close.toast") });
      setCloseOpen(false);
      setCloseSummary("");
      setCloseActions("");
      setUnblockedCard(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        showToast({ kind: "error", text: t("fleetIncidents.errors.noPermission") });
        return;
      }
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleetIncidents.errors.actionFailed") });
    } finally {
      setIsSubmitting(false);
    }
  }, [closeActions, closeSummary, id, showToast, t, unblockedCard, user?.token]);

  if (!canView) {
    return <AppForbiddenState message={t("fleetIncidents.errors.noPermission")} />;
  }

  if (!id) {
    return <AppEmptyState title={t("fleetIncidents.details.notFound")} description={t("fleetIncidents.details.notFoundHint")} />;
  }

  if (loading) {
    return (
      <div className="page">
        <div className="page-header">
          <h1>{t("fleetIncidents.details.title")}</h1>
        </div>
        <div className="card state">{t("common.loading")}</div>
      </div>
    );
  }

  if (isForbidden) {
    return <AppForbiddenState message={t("fleetIncidents.errors.noPermission")} />;
  }

  if (unavailable) {
    return <FleetUnavailableState />;
  }

  if (error) {
    return <AppErrorState message={error} onRetry={() => void loadDetails()} />;
  }

  if (!details) {
    return <AppEmptyState title={t("fleetIncidents.details.notFound")} description={t("fleetIncidents.details.notFoundRetry")} />;
  }

  const timeline = details.timeline ?? [];
  const resolution = details.resolution;
  const showResolution = details.status === "CLOSED" || Boolean(resolution?.summary);
  const statusLabel =
    details.status === "OPEN"
      ? t("fleetIncidents.status.open")
      : details.status === "IN_PROGRESS"
        ? t("fleetIncidents.status.inProgress")
        : details.status === "CLOSED"
          ? t("fleetIncidents.status.closed")
          : details.status ?? "—";

  return (
    <div className="stack">
      <section className="card">
        <div className="card__header">
          <div>
            <h2>{details.title}</h2>
            <p className="muted">{t("fleetIncidents.details.caseId", { id: details.case_id })}</p>
          </div>
          <div className="actions">
            {showStartButton ? (
              <button type="button" className="primary" onClick={() => setStartOpen(true)}>
                {t("fleetIncidents.actions.start")}
              </button>
            ) : null}
            {showCloseButton ? (
              <button type="button" className="primary" onClick={() => setCloseOpen(true)}>
                {t("fleetIncidents.actions.close")}
              </button>
            ) : null}
            <Link className="ghost" to="/fleet/incidents">
              {t("fleetIncidents.actions.back")}
            </Link>
          </div>
        </div>
        <div className="meta-grid">
          <div>
            <div className="label">{t("fleetIncidents.fields.status")}</div>
            <span className={getFleetCaseStatusBadgeClass(details.status)}>
              {statusLabel}
            </span>
          </div>
          <div>
            <div className="label">{t("fleetIncidents.fields.severity")}</div>
            <span className={getFleetCaseSeverityBadgeClass(details.severity)}>{details.severity ?? "—"}</span>
          </div>
          <div>
            <div className="label">{t("fleetIncidents.fields.scope")}</div>
            {scopeLink ? <Link to={scopeLink}>{scopeLabel}</Link> : <div>{scopeLabel}</div>}
          </div>
          <div>
            <div className="label">{t("fleetIncidents.fields.policyAction")}</div>
            <span className={getFleetCasePolicyActionBadgeClass(policyAction)}>{policyAction ?? "—"}</span>
          </div>
          <div>
            <div className="label">{t("fleetIncidents.fields.openedAt")}</div>
            <div>{details.opened_at ? formatDateTime(details.opened_at) : "—"}</div>
          </div>
          <div>
            <div className="label">{t("fleetIncidents.fields.updatedAt")}</div>
            <div>{details.last_updated_at ? formatDateTime(details.last_updated_at) : "—"}</div>
          </div>
          <div>
            <div className="label">{t("fleetIncidents.fields.trigger")}</div>
            <span className={getFleetCaseTriggerBadgeClass(trigger)}>
              {trigger === "LIMIT_BREACH"
                ? t("fleetIncidents.triggers.limitBreach")
                : trigger === "ANOMALY"
                  ? t("fleetIncidents.triggers.anomaly")
                  : trigger ?? "—"}
            </span>
          </div>
          <div>
            <div className="label">{t("fleetIncidents.fields.assigned")}</div>
            <div>{details.assigned_to ?? "—"}</div>
          </div>
        </div>
      </section>

      <section className="card">
        <h3>{t("fleetIncidents.explain.title")}</h3>
        <div className="meta-grid">
          <div>
            <div className="label">{t("fleetIncidents.explain.trigger")}</div>
            <div>{trigger ?? "—"}</div>
          </div>
          <div>
            <div className="label">{t("fleetIncidents.explain.rule")}</div>
            <div>{details.explain?.rule_name ?? "—"}</div>
          </div>
          <div>
            <div className="label">{t("fleetIncidents.explain.observed")}</div>
            <div>{details.explain?.observed ?? "—"}</div>
          </div>
          <div>
            <div className="label">{t("fleetIncidents.explain.threshold")}</div>
            <div>{details.explain?.threshold ?? "—"}</div>
          </div>
          <div>
            <div className="label">{t("fleetIncidents.explain.baseline")}</div>
            <div>{details.explain?.baseline ?? "—"}</div>
          </div>
          <div>
            <div className="label">{t("fleetIncidents.explain.occurredAt")}</div>
            <div>{details.explain?.occurred_at ? formatDateTime(details.explain.occurred_at) : "—"}</div>
          </div>
          <div>
            <div className="label">{t("fleetIncidents.explain.policy")}</div>
            <div>{details.explain?.policy_name ?? "—"}</div>
          </div>
          <div>
            <div className="label">{t("fleetIncidents.explain.cooldown")}</div>
            <div>
              {details.explain?.cooldown_seconds !== null && details.explain?.cooldown_seconds !== undefined
                ? t("fleetIncidents.explain.cooldownValue", { value: details.explain.cooldown_seconds })
                : "—"}
            </div>
          </div>
        </div>
        {details.explain?.context ? <p className="muted">{details.explain.context}</p> : null}
      </section>

      <section className="card">
        <h3>{t("fleetIncidents.timeline.title")}</h3>
        {timeline.length === 0 ? (
          <AppEmptyState title={t("fleetIncidents.timeline.emptyTitle")} description={t("fleetIncidents.timeline.emptyDescription")} />
        ) : (
          <div className="timeline-list">
            {timeline.map((event, index) => {
              const title = event.title ?? event.description ?? t("fleetIncidents.timeline.eventFallback");
              const timestamp = resolveTimelineTimestamp(event);
              return (
                <div className="timeline-item" key={`${event.id ?? title}-${index}`}>
                  <div className="timeline-item__meta">
                    <span className="timeline-item__title">{title}</span>
                    <span className="muted small">{timestamp ? formatDateTime(timestamp) : "—"}</span>
                  </div>
                  {event.description && event.title ? <div className="timeline-item__body">{event.description}</div> : null}
                  {event.link ? (
                    <div className="timeline-item__refs">
                      <Link to={event.link}>{t("fleetIncidents.timeline.link")}</Link>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        )}
      </section>

      {showResolution ? (
        <section className="card">
          <h3>{t("fleetIncidents.resolution.title")}</h3>
          <div className="meta-grid">
            <div>
              <div className="label">{t("fleetIncidents.resolution.summary")}</div>
              <div>{resolution?.summary ?? "—"}</div>
            </div>
            <div>
              <div className="label">{t("fleetIncidents.resolution.reason")}</div>
              <div>{resolution?.reason ?? "—"}</div>
            </div>
            <div>
              <div className="label">{t("fleetIncidents.resolution.actions")}</div>
              <div>{resolution?.actions_taken ?? "—"}</div>
            </div>
            <div>
              <div className="label">{t("fleetIncidents.resolution.closedBy")}</div>
              <div>{resolution?.closed_by ?? "—"}</div>
            </div>
            <div>
              <div className="label">{t("fleetIncidents.resolution.closedAt")}</div>
              <div>{resolution?.closed_at ? formatDateTime(resolution.closed_at) : "—"}</div>
            </div>
          </div>
        </section>
      ) : null}

      <section className="card">
        <h3>{t("fleetIncidents.audit.title")}</h3>
        <div className="meta-grid">
          <div>
            <div className="label">{t("fleetIncidents.audit.eventId")}</div>
            <div>{details.audit_event_id ?? "—"}</div>
          </div>
          <div>
            <div className="label">{t("fleetIncidents.audit.decisionId")}</div>
            <div>{details.decision_memory_id ?? "—"}</div>
          </div>
          <div>
            <div className="label">{t("fleetIncidents.audit.sourceRef")}</div>
            <div>{details.source?.ref_id ?? "—"}</div>
          </div>
        </div>
      </section>

      <ConfirmActionModal
        isOpen={startOpen}
        title={t("fleetIncidents.start.title")}
        description={t("fleetIncidents.start.description")}
        confirmLabel={t("fleetIncidents.start.confirm")}
        cancelLabel={t("fleetIncidents.start.cancel")}
        onConfirm={() => void handleStart()}
        onCancel={() => setStartOpen(false)}
        isProcessing={isSubmitting}
      >
        <label className="filter">
          {t("fleetIncidents.start.note")}
          <textarea value={startNote} onChange={(event) => setStartNote(event.target.value)} rows={3} />
        </label>
      </ConfirmActionModal>

      <ConfirmActionModal
        isOpen={closeOpen}
        title={t("fleetIncidents.close.title")}
        description={t("fleetIncidents.close.description")}
        confirmLabel={t("fleetIncidents.close.confirm")}
        cancelLabel={t("fleetIncidents.close.cancel")}
        onConfirm={() => void handleClose()}
        onCancel={() => setCloseOpen(false)}
        isProcessing={isSubmitting}
        isConfirmDisabled={isSubmitting}
      >
        <div className="stack">
          <label className="filter">
            {t("fleetIncidents.close.summary")}
            <input
              value={closeSummary}
              onChange={(event) => setCloseSummary(event.target.value)}
              placeholder={t("fleetIncidents.close.summaryPlaceholder")}
            />
          </label>
          <label className="filter">
            {t("fleetIncidents.close.actions")}
            <textarea
              value={closeActions}
              onChange={(event) => setCloseActions(event.target.value)}
              placeholder={t("fleetIncidents.close.actionsPlaceholder")}
              rows={3}
            />
          </label>
          {policyAction && policyAction.toString().toUpperCase().includes("AUTO_BLOCK") ? (
            <label className="filter">
              <input
                type="checkbox"
                checked={unblockedCard}
                onChange={(event) => setUnblockedCard(event.target.checked)}
              />
              {t("fleetIncidents.close.unblocked")}
            </label>
          ) : null}
          {validationError ? <div className="error-text">{validationError}</div> : null}
        </div>
      </ConfirmActionModal>

      {toast ? <Toast toast={toast} onClose={() => showToast(null)} /> : null}
    </div>
  );
}
