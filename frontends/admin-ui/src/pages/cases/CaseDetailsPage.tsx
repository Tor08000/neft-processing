import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  closeAdminCase,
  fetchAdminCaseDetails,
  fetchAdminCaseEvents,
  isNotAvailableError,
  updateAdminCaseStatus,
  type CaseDetailsResponse,
  type CaseEvent,
  type CaseSnapshot,
  type CaseStatus,
} from "../../api/adminCases";
import { UnauthorizedError } from "../../api/client";
import { computeExplainScore } from "../../gamification/score";
import type { ExplainV2Response } from "../../types/explainV2";
import { recordActionApplied, recordCaseClosed } from "../../mastery/events";
import { Tabs } from "../../components/common/Tabs";
import { JsonViewer } from "../../components/common/JsonViewer";
import { CloseCaseModal, getSelectedActionsCount } from "../../components/cases/CloseCaseModal";
import { Toast } from "../../components/common/Toast";
import { useToast } from "../../components/Toast/useToast";

const statusTone = (status: CaseStatus) => {
  if (status === "CLOSED") return "badge badge-danger";
  if (status === "IN_PROGRESS") return "badge badge-success";
  return "badge";
};

const formatTimestamp = (value?: string | null) => {
  if (!value) return "—";
  return new Date(value).toLocaleString("ru-RU");
};

const resolveTitle = (id: string, kind?: string | null, title?: string | null) =>
  title ?? (kind ? `${kind} · ${id}` : `Case ${id}`);

const isForbidden = (error: unknown) => error instanceof Error && /HTTP 403\b/.test(error.message);

const toScoreSnapshot = (snapshot?: CaseSnapshot | null) => {
  const explain = snapshot?.explain_snapshot as ExplainV2Response | null | undefined;
  if (!explain) return undefined;
  return computeExplainScore(explain);
};

const sortSnapshots = (snapshots?: CaseSnapshot[] | null) =>
  (snapshots ?? []).slice().sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());

export function CaseDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const { toast, showToast } = useToast();
  const [payload, setPayload] = useState<CaseDetailsResponse | null>(null);
  const [events, setEvents] = useState<CaseEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isEventsLoading, setIsEventsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [unauthorized, setUnauthorized] = useState(false);
  const [notAvailable, setNotAvailable] = useState(false);
  const [actionsAvailable, setActionsAvailable] = useState(true);
  const [eventsAvailable, setEventsAvailable] = useState(true);
  const [closeOpen, setCloseOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("explain");
  const [isStatusUpdating, setIsStatusUpdating] = useState(false);

  const loadDetails = useCallback(() => {
    if (!id) return;
    setIsLoading(true);
    setError(null);
    setUnauthorized(false);
    fetchAdminCaseDetails(id)
      .then((data) => {
        setPayload(data);
        setNotAvailable(false);
        setActionsAvailable(true);
      })
      .catch((err: unknown) => {
        if (err instanceof UnauthorizedError || isForbidden(err)) {
          setUnauthorized(true);
          return;
        }
      if (isNotAvailableError(err)) {
        setNotAvailable(true);
        return;
      }
        setError((err as Error).message);
      })
      .finally(() => setIsLoading(false));
  }, [id]);

  const loadEvents = useCallback(() => {
    if (!id) return;
    setIsEventsLoading(true);
    fetchAdminCaseEvents(id)
      .then((data) => {
        setEvents(data.items ?? []);
        setEventsAvailable(true);
      })
      .catch((err: unknown) => {
        if (isNotAvailableError(err)) {
          setEventsAvailable(false);
          return;
        }
        setEventsAvailable(true);
      })
      .finally(() => setIsEventsLoading(false));
  }, [id]);

  useEffect(() => {
    loadDetails();
    loadEvents();
  }, [loadDetails, loadEvents]);

  const snapshotsSorted = useMemo(() => sortSnapshots(payload?.snapshots), [payload?.snapshots]);
  const firstSnapshot = snapshotsSorted[0];
  const lastSnapshot = snapshotsSorted[snapshotsSorted.length - 1] ?? payload?.latest_snapshot;
  const selectedActionsCount = getSelectedActionsCount(lastSnapshot);

  const tabOptions = useMemo(
    () => [
      { id: "explain", label: "Explain JSON" },
      { id: "diff", label: "Diff JSON" },
      { id: "actions", label: "Selected actions" },
    ],
    [],
  );

  const handleCopyLink = useCallback(() => {
    void navigator.clipboard.writeText(window.location.href);
    showToast("success", "Link copied");
  }, [showToast]);

  const handleMarkInProgress = async () => {
    if (!id || !payload) return;
    setIsStatusUpdating(true);
    try {
      const response = await updateAdminCaseStatus(id, "IN_PROGRESS");
      if (response) {
        setPayload((prev) => (prev ? { ...prev, case: response } : prev));
      } else {
        setPayload((prev) => (prev ? { ...prev, case: { ...prev.case, status: "IN_PROGRESS" } } : prev));
      }
      showToast("success", "Status updated");
    } catch (err) {
      if (isNotAvailableError(err)) {
        setActionsAvailable(false);
        showToast("error", "Not available in this environment");
      } else {
        showToast("error", (err as Error).message);
      }
    } finally {
      setIsStatusUpdating(false);
    }
  };

  const handleClose = async (payloadInput: { resolutionNote: string; actionsApplied: boolean }) => {
    if (!id || !payload) return;
    try {
      const response = await closeAdminCase(id, {
        resolution_note: payloadInput.resolutionNote,
        resolution_code: null,
      });
      const updatedCase =
        response ?? {
          ...payload.case,
          status: "CLOSED" as CaseStatus,
          closed_at: new Date().toISOString(),
        };
      setPayload((prev) => (prev ? { ...prev, case: { ...prev.case, ...updatedCase } } : prev));
      setCloseOpen(false);
      const scoreSnapshot = toScoreSnapshot(lastSnapshot);
      recordCaseClosed(id, { scoreSnapshot });
      if (payloadInput.actionsApplied) {
        const scoreBefore = toScoreSnapshot(firstSnapshot);
        const scoreAfter = snapshotsSorted.length > 1 ? toScoreSnapshot(lastSnapshot) : undefined;
        recordActionApplied({
          caseId: id,
          selectedActionsCount,
          scoreBefore,
          scoreAfter,
        });
      }
      showToast("success", "Case closed");
    } catch (err) {
      if (isNotAvailableError(err)) {
        setActionsAvailable(false);
        const message = "Not available in this environment";
        showToast("error", message);
        throw new Error(message);
      } else {
        const message = (err as Error).message;
        showToast("error", message);
        throw new Error(message);
      }
    }
  };

  if (!id) {
    return <div className="card">Case not found</div>;
  }

  if (unauthorized) {
    return <div className="card error-state">Not authorized</div>;
  }

  if (notAvailable) {
    return <div className="card">Not available in this environment</div>;
  }

  if (isLoading) {
    return <div className="card">Loading case...</div>;
  }

  if (error) {
    return <div className="card error-state">{error}</div>;
  }

  if (!payload) {
    return <div className="card">Case not found</div>;
  }

  const activeSnapshot = lastSnapshot ?? payload.latest_snapshot;

  return (
    <div className="stack">
      <Toast toast={toast} />
      <section className="card">
        <div className="card__header">
          <div>
            <h2>{resolveTitle(payload.case.id, payload.case.kind, payload.case.title)}</h2>
            <p className="muted">Case ID: {payload.case.id}</p>
          </div>
          <div className="stack-inline">
            <button type="button" className="ghost" onClick={handleCopyLink}>
              Copy link
            </button>
            <Link className="ghost" to="/cases">
              Back to cases
            </Link>
          </div>
        </div>
        <div className="meta-grid">
          <div>
            <div className="label">Status</div>
            <span className={statusTone(payload.case.status)}>{payload.case.status}</span>
          </div>
          <div>
            <div className="label">Priority</div>
            <span className="badge">{payload.case.priority ?? "—"}</span>
          </div>
          <div>
            <div className="label">Created</div>
            <div>{formatTimestamp(payload.case.created_at)}</div>
          </div>
          <div>
            <div className="label">Created by</div>
            <div>{payload.case.created_by ?? "—"}</div>
          </div>
          <div>
            <div className="label">Closed</div>
            <div>{formatTimestamp(payload.case.closed_at)}</div>
          </div>
          <div>
            <div className="label">Closed by</div>
            <div>{payload.case.closed_by ?? "—"}</div>
          </div>
        </div>
        <div className="stack-inline" style={{ marginTop: 16 }}>
          <button
            type="button"
            className="neft-btn-secondary"
            onClick={handleMarkInProgress}
            disabled={payload.case.status !== "OPEN" || isStatusUpdating || !actionsAvailable}
            title={!actionsAvailable ? "Not available in this environment" : undefined}
          >
            Mark In Progress
          </button>
          <button
            type="button"
            className="neft-btn-primary"
            onClick={() => setCloseOpen(true)}
            disabled={payload.case.status === "CLOSED" || !actionsAvailable}
            title={!actionsAvailable ? "Not available in this environment" : undefined}
          >
            Close Case
          </button>
        </div>
      </section>

      <section className="card">
        <h3>Summary</h3>
        <div className="stack" style={{ gap: 12 }}>
          <div>
            <div className="label">Note</div>
            <div>{payload.case.note ?? "—"}</div>
          </div>
          <div className="meta-grid">
            <div>
              <div className="label">Updated</div>
              <div>{formatTimestamp(payload.case.updated_at)}</div>
            </div>
            <div>
              <div className="label">Kind</div>
              <div>{payload.case.kind ?? "—"}</div>
            </div>
          </div>
        </div>
      </section>

      <section className="card">
        <h3>Snapshots / Evidence</h3>
        {activeSnapshot ? (
          <div>
            <Tabs tabs={tabOptions} active={activeTab} onChange={setActiveTab} />
            {activeTab === "explain" ? (
              <JsonViewer title="Explain JSON" value={activeSnapshot.explain_snapshot} />
            ) : null}
            {activeTab === "diff" ? (
              activeSnapshot.diff_snapshot ? (
                <JsonViewer title="Diff JSON" value={activeSnapshot.diff_snapshot} />
              ) : (
                <div className="muted">Diff snapshot not available</div>
              )
            ) : null}
            {activeTab === "actions" ? (
              activeSnapshot.selected_actions ? (
                <JsonViewer title="Selected actions" value={activeSnapshot.selected_actions} />
              ) : (
                <div className="muted">No selected actions</div>
              )
            ) : null}
          </div>
        ) : (
          <div className="muted">Snapshots not available</div>
        )}
      </section>

      <section className="card">
        <h3>Timeline / Events</h3>
        {!eventsAvailable ? (
          <div className="muted">Events not available</div>
        ) : isEventsLoading ? (
          <div className="muted">Loading events...</div>
        ) : events.length === 0 ? (
          <div className="muted">No events yet</div>
        ) : (
          <div className="timeline-list">
            {events.map((event) => (
              <div className="timeline-item" key={event.id}>
                <div className="timeline-item__meta">
                  <span className="timeline-item__title">{event.actor ?? "System"}</span>
                  <span className="muted small">{formatTimestamp(event.created_at)}</span>
                </div>
                <div className="timeline-item__body">
                  <strong>{event.type}</strong>
                  {event.note ? ` · ${event.note}` : ""}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <CloseCaseModal
        open={closeOpen}
        caseItem={payload.case}
        selectedActionsCount={selectedActionsCount}
        onCancel={() => setCloseOpen(false)}
        onSubmit={handleClose}
      />
    </div>
  );
}

export default CaseDetailsPage;
