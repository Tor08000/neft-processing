import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  changeCommercialPlan,
  disableCommercialAddon,
  enableCommercialAddon,
  getCommercialEntitlements,
  getCommercialState,
  recomputeCommercialEntitlements,
  removeCommercialOverride,
  upsertCommercialOverride,
} from "../../api/commercial";
import { UnauthorizedError } from "../../api/http";
import { useAuth } from "../../auth/AuthContext";
import type {
  CommercialEntitlementsSnapshot,
  CommercialOrgState,
  CommercialOverride,
} from "../../types/commercial";

type DiffEntry = {
  path: string;
  before: unknown;
  after: unknown;
};

const MAX_DIFF_ENTRIES = 40;

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const diffObjects = (before: unknown, after: unknown, path = ""): DiffEntry[] => {
  if (before === after) {
    return [];
  }
  if (typeof before !== typeof after) {
    return [{ path, before, after }];
  }
  if (Array.isArray(before) && Array.isArray(after)) {
    if (before.length !== after.length) {
      return [{ path, before, after }];
    }
    return before.flatMap((item, index) =>
      diffObjects(item, after[index], path ? `${path}[${index}]` : `[${index}]`),
    );
  }
  if (isRecord(before) && isRecord(after)) {
    const keys = new Set([...Object.keys(before), ...Object.keys(after)]);
    const diffs: DiffEntry[] = [];
    keys.forEach((key) => {
      diffs.push(
        ...diffObjects(
          before[key],
          after[key],
          path ? `${path}.${key}` : key,
        ),
      );
    });
    return diffs;
  }
  return [{ path, before, after }];
};

const formatJson = (value: unknown) => JSON.stringify(value, null, 2);

export const CommercialOrgPage: React.FC = () => {
  const { accessToken, logout } = useAuth();
  const navigate = useNavigate();
  const params = useParams();
  const initialOrgId = params.orgId ? Number(params.orgId) : null;
  const [orgIdInput, setOrgIdInput] = useState(initialOrgId ? String(initialOrgId) : "");
  const [orgId, setOrgId] = useState<number | null>(initialOrgId);
  const [state, setState] = useState<CommercialOrgState | null>(null);
  const [snapshots, setSnapshots] = useState<CommercialEntitlementsSnapshot[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editMode, setEditMode] = useState(false);

  const [planForm, setPlanForm] = useState({
    plan_code: "",
    plan_version: "",
    billing_cycle: "",
    status: "",
    reason: "",
  });
  const [addonForm, setAddonForm] = useState({
    addon_code: "",
    status: "ACTIVE",
    reason: "",
  });
  const [overrideForm, setOverrideForm] = useState({
    feature_key: "",
    availability: "ENABLED",
    limits_json: "",
    reason: "",
    confirm: false,
  });
  const [overrideRemoveForm, setOverrideRemoveForm] = useState({
    feature_key: "",
    reason: "",
    confirm: false,
  });
  const [recomputeReason, setRecomputeReason] = useState("");

  const loadOrg = useCallback(
    async (targetOrgId: number) => {
      if (!accessToken) return;
      setLoading(true);
      setError(null);
      try {
        const [stateResponse, entitlementsResponse] = await Promise.all([
          getCommercialState(accessToken, targetOrgId),
          getCommercialEntitlements(accessToken, targetOrgId),
        ]);
        setState(stateResponse);
        const snapshotList = [
          ...(entitlementsResponse.current ? [entitlementsResponse.current] : []),
          ...entitlementsResponse.previous,
        ];
        setSnapshots(snapshotList);
      } catch (err) {
        console.error("Ошибка загрузки коммерции", err);
        if (err instanceof UnauthorizedError) {
          logout();
          return;
        }
        setError("Не удалось загрузить коммерческое состояние.");
      } finally {
        setLoading(false);
      }
    },
    [accessToken, logout],
  );

  useEffect(() => {
    if (orgId) {
      loadOrg(orgId);
    }
  }, [loadOrg, orgId]);

  useEffect(() => {
    if (!state?.subscription) return;
    setPlanForm((prev) => ({
      ...prev,
      plan_code: state.subscription?.plan_code ?? "",
      plan_version: state.subscription?.plan_version ? String(state.subscription.plan_version) : "",
      billing_cycle: state.subscription?.billing_cycle ?? "",
      status: state.subscription?.status ?? "",
    }));
  }, [state]);

  const currentSnapshot = snapshots[0] ?? null;
  const previousSnapshots = snapshots.slice(1);

  const diffs = useMemo(() => {
    return previousSnapshots.map((snapshot, index) => {
      const base = snapshots[index];
      if (!base) {
        return [];
      }
      const entries = diffObjects(snapshot.entitlements, base.entitlements);
      return entries.slice(0, MAX_DIFF_ENTRIES);
    });
  }, [previousSnapshots, snapshots]);

  const handleLoad = (event: React.FormEvent) => {
    event.preventDefault();
    const parsed = Number(orgIdInput);
    if (Number.isNaN(parsed) || parsed <= 0) {
      setError("Введите корректный org_id.");
      return;
    }
    setOrgId(parsed);
    navigate(`/commercial/${parsed}`);
  };

  const requireConfirm = (message: string) => window.confirm(message);

  const handlePlanUpdate = async () => {
    if (!accessToken || !orgId) return;
    if (!requireConfirm("Изменить план организации?")) return;
    try {
      await changeCommercialPlan(accessToken, orgId, {
        plan_code: planForm.plan_code.trim(),
        plan_version: Number(planForm.plan_version),
        billing_cycle: planForm.billing_cycle.trim(),
        status: planForm.status.trim(),
        reason: planForm.reason.trim() || null,
      });
      await loadOrg(orgId);
    } catch (err) {
      console.error("Ошибка смены плана", err);
      setError("Не удалось изменить план.");
    }
  };

  const handleAddonUpdate = async () => {
    if (!accessToken || !orgId) return;
    if (!requireConfirm("Обновить add-on?")) return;
    try {
      if (addonForm.status === "ACTIVE") {
        await enableCommercialAddon(accessToken, orgId, {
          addon_code: addonForm.addon_code.trim(),
          status: "ACTIVE",
          reason: addonForm.reason.trim() || null,
        });
      } else {
        await disableCommercialAddon(accessToken, orgId, {
          addon_code: addonForm.addon_code.trim(),
          reason: addonForm.reason.trim() || null,
        });
      }
      await loadOrg(orgId);
    } catch (err) {
      console.error("Ошибка обновления add-on", err);
      setError("Не удалось обновить add-on.");
    }
  };

  const handleOverrideUpsert = async () => {
    if (!accessToken || !orgId) return;
    if (!requireConfirm("Применить override?")) return;
    if (!overrideForm.reason.trim() || !overrideForm.confirm) {
      setError("Укажите reason и подтвердите override.");
      return;
    }
    try {
      const limitsJson = overrideForm.limits_json.trim();
      const parsedLimits =
        limitsJson.length > 0 ? (JSON.parse(limitsJson) as Record<string, unknown>) : null;
      await upsertCommercialOverride(accessToken, orgId, {
        feature_key: overrideForm.feature_key.trim(),
        availability: overrideForm.availability.trim(),
        limits_json: parsedLimits,
        reason: overrideForm.reason.trim(),
        confirm: overrideForm.confirm,
      });
      await loadOrg(orgId);
    } catch (err) {
      console.error("Ошибка override", err);
      setError("Не удалось применить override.");
    }
  };

  const handleOverrideRemove = async () => {
    if (!accessToken || !orgId) return;
    if (!requireConfirm("Удалить override?")) return;
    if (!overrideRemoveForm.reason.trim() || !overrideRemoveForm.confirm) {
      setError("Укажите reason и подтвердите удаление override.");
      return;
    }
    try {
      await removeCommercialOverride(
        accessToken,
        orgId,
        overrideRemoveForm.feature_key.trim(),
        overrideRemoveForm.reason.trim(),
      );
      await loadOrg(orgId);
    } catch (err) {
      console.error("Ошибка удаления override", err);
      setError("Не удалось удалить override.");
    }
  };

  const handleRecompute = async () => {
    if (!accessToken || !orgId) return;
    if (!requireConfirm("Пересчитать entitlements snapshot?")) return;
    try {
      await recomputeCommercialEntitlements(accessToken, orgId, { reason: recomputeReason.trim() || null });
      await loadOrg(orgId);
    } catch (err) {
      console.error("Ошибка recompute", err);
      setError("Не удалось пересчитать entitlements.");
    }
  };

  const overridesByKey = useMemo(() => {
    const map = new Map<string, CommercialOverride>();
    (state?.overrides ?? []).forEach((override) => {
      map.set(override.feature_key, override);
    });
    return map;
  }, [state]);

  return (
    <div className="stack">
      <div className="page-header">
        <div>
          <h2>Commercial control</h2>
          <p className="muted">Single source of truth для коммерции и доступов.</p>
        </div>
        <button
          type="button"
          className={editMode ? "button neft-btn-primary" : "button neft-btn-secondary"}
          onClick={() => setEditMode((prev) => !prev)}
        >
          {editMode ? "Режим чтения" : "Режим редактирования"}
        </button>
      </div>

      <form className="card" onSubmit={handleLoad} style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <label className="label" htmlFor="org-id">
          Org ID
        </label>
        <input
          id="org-id"
          className="neft-input neft-focus-ring"
          value={orgIdInput}
          onChange={(event) => setOrgIdInput(event.target.value)}
          placeholder="1234"
          style={{ maxWidth: 200 }}
        />
        <button type="submit" className="button neft-btn-primary">
          Загрузить
        </button>
      </form>

      {error && <div className="card error-state">{error}</div>}

      {loading && <div className="card">Загрузка...</div>}

      {state && (
        <>
          <div className="card stack">
            <h3>Организация</h3>
            <div>Org ID: {state.org.id}</div>
            <div>Название: {state.org.name ?? "—"}</div>
            <div>Статус: {state.org.status ?? "—"}</div>
          </div>

          <div className="card stack">
            <h3>Текущий план</h3>
            <div>Код: {state.subscription?.plan_code ?? "—"}</div>
            <div>Версия: {state.subscription?.plan_version ?? "—"}</div>
            <div>Billing: {state.subscription?.billing_cycle ?? "—"}</div>
            <div>Статус: {state.subscription?.status ?? "—"}</div>
            <div>Support: {state.subscription?.support_plan ?? "—"}</div>
            <div>SLO tier: {state.subscription?.slo_tier ?? "—"}</div>
            <p className="muted">Изменения вступают в силу после recompute entitlements.</p>
            <div className="grid" style={{ gap: 12 }}>
              <div>
                <label className="label">Plan code</label>
                <input
                  className="neft-input neft-focus-ring"
                  value={planForm.plan_code}
                  onChange={(event) => setPlanForm((prev) => ({ ...prev, plan_code: event.target.value }))}
                  disabled={!editMode}
                />
              </div>
              <div>
                <label className="label">Plan version</label>
                <input
                  className="neft-input neft-focus-ring"
                  value={planForm.plan_version}
                  onChange={(event) => setPlanForm((prev) => ({ ...prev, plan_version: event.target.value }))}
                  disabled={!editMode}
                />
              </div>
              <div>
                <label className="label">Billing cycle</label>
                <input
                  className="neft-input neft-focus-ring"
                  value={planForm.billing_cycle}
                  onChange={(event) => setPlanForm((prev) => ({ ...prev, billing_cycle: event.target.value }))}
                  disabled={!editMode}
                />
              </div>
              <div>
                <label className="label">Status</label>
                <input
                  className="neft-input neft-focus-ring"
                  value={planForm.status}
                  onChange={(event) => setPlanForm((prev) => ({ ...prev, status: event.target.value }))}
                  disabled={!editMode}
                />
              </div>
            </div>
            <label className="label">Reason</label>
            <input
              className="neft-input neft-focus-ring"
              value={planForm.reason}
              onChange={(event) => setPlanForm((prev) => ({ ...prev, reason: event.target.value }))}
              disabled={!editMode}
            />
            <button type="button" className="button neft-btn-primary" disabled={!editMode} onClick={handlePlanUpdate}>
              Изменить план
            </button>
          </div>

          <div className="card stack">
            <h3>Add-ons</h3>
            {state.addons.length === 0 ? (
              <div className="muted">Add-ons отсутствуют.</div>
            ) : (
              <ul>
                {state.addons.map((addon) => (
                  <li key={addon.addon_code}>
                    {addon.addon_code}: {addon.status}
                  </li>
                ))}
              </ul>
            )}
            <p className="muted">Изменения вступают в силу после recompute entitlements.</p>
            <div className="grid" style={{ gap: 12 }}>
              <div>
                <label className="label">Add-on code</label>
                <input
                  className="neft-input neft-focus-ring"
                  value={addonForm.addon_code}
                  onChange={(event) => setAddonForm((prev) => ({ ...prev, addon_code: event.target.value }))}
                  disabled={!editMode}
                />
              </div>
              <div>
                <label className="label">Status</label>
                <select
                  className="neft-input neft-focus-ring"
                  value={addonForm.status}
                  onChange={(event) => setAddonForm((prev) => ({ ...prev, status: event.target.value }))}
                  disabled={!editMode}
                >
                  <option value="ACTIVE">ACTIVE</option>
                  <option value="DISABLED">DISABLED</option>
                </select>
              </div>
            </div>
            <label className="label">Reason</label>
            <input
              className="neft-input neft-focus-ring"
              value={addonForm.reason}
              onChange={(event) => setAddonForm((prev) => ({ ...prev, reason: event.target.value }))}
              disabled={!editMode}
            />
            <button type="button" className="button neft-btn-primary" disabled={!editMode} onClick={handleAddonUpdate}>
              Обновить add-on
            </button>
          </div>

          <div className="card stack">
            <h3>Overrides</h3>
            {state.overrides.length === 0 ? (
              <div className="muted">Overrides отсутствуют.</div>
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Feature</th>
                    <th>Availability</th>
                    <th>Limits</th>
                  </tr>
                </thead>
                <tbody>
                  {state.overrides.map((override) => (
                    <tr key={override.feature_key}>
                      <td>{override.feature_key}</td>
                      <td>{override.availability}</td>
                      <td>
                        <pre style={{ margin: 0 }}>{override.limits_json ? formatJson(override.limits_json) : "—"}</pre>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <p className="muted">Override требует reason и подтверждения.</p>
            <div className="grid" style={{ gap: 12 }}>
              <div>
                <label className="label">Feature</label>
                <input
                  className="neft-input neft-focus-ring"
                  value={overrideForm.feature_key}
                  onChange={(event) => setOverrideForm((prev) => ({ ...prev, feature_key: event.target.value }))}
                  disabled={!editMode}
                />
              </div>
              <div>
                <label className="label">Availability</label>
                <input
                  className="neft-input neft-focus-ring"
                  value={overrideForm.availability}
                  onChange={(event) => setOverrideForm((prev) => ({ ...prev, availability: event.target.value }))}
                  disabled={!editMode}
                />
              </div>
            </div>
            <label className="label">Limits JSON</label>
            <textarea
              className="neft-input neft-focus-ring"
              value={overrideForm.limits_json}
              onChange={(event) => setOverrideForm((prev) => ({ ...prev, limits_json: event.target.value }))}
              disabled={!editMode}
              rows={4}
            />
            <label className="label">Reason</label>
            <input
              className="neft-input neft-focus-ring"
              value={overrideForm.reason}
              onChange={(event) => setOverrideForm((prev) => ({ ...prev, reason: event.target.value }))}
              disabled={!editMode}
            />
            <label className="label" style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input
                type="checkbox"
                checked={overrideForm.confirm}
                onChange={(event) => setOverrideForm((prev) => ({ ...prev, confirm: event.target.checked }))}
                disabled={!editMode}
              />
              Подтверждаю override
            </label>
            <button type="button" className="button neft-btn-primary" disabled={!editMode} onClick={handleOverrideUpsert}>
              Применить override
            </button>

            <hr />

            <div className="grid" style={{ gap: 12 }}>
              <div>
                <label className="label">Feature for remove</label>
                <input
                  className="neft-input neft-focus-ring"
                  value={overrideRemoveForm.feature_key}
                  onChange={(event) => setOverrideRemoveForm((prev) => ({ ...prev, feature_key: event.target.value }))}
                  disabled={!editMode}
                />
              </div>
              <div>
                <label className="label">Reason</label>
                <input
                  className="neft-input neft-focus-ring"
                  value={overrideRemoveForm.reason}
                  onChange={(event) => setOverrideRemoveForm((prev) => ({ ...prev, reason: event.target.value }))}
                  disabled={!editMode}
                />
              </div>
            </div>
            <label className="label" style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input
                type="checkbox"
                checked={overrideRemoveForm.confirm}
                onChange={(event) => setOverrideRemoveForm((prev) => ({ ...prev, confirm: event.target.checked }))}
                disabled={!editMode}
              />
              Подтверждаю удаление override
            </label>
            <button
              type="button"
              className="button neft-btn-secondary"
              disabled={!editMode || !overrideRemoveForm.confirm}
              onClick={handleOverrideRemove}
            >
              Удалить override
            </button>
          </div>

          <div className="card stack">
            <h3>Entitlements snapshots</h3>
            <div>
              Текущий snapshot: {state.entitlements_snapshot?.hash ?? "—"} (версия{" "}
              {state.entitlements_snapshot?.version ?? "—"})
            </div>
            <label className="label">Reason for recompute</label>
            <input
              className="neft-input neft-focus-ring"
              value={recomputeReason}
              onChange={(event) => setRecomputeReason(event.target.value)}
              disabled={!editMode}
            />
            <button type="button" className="button neft-btn-primary" disabled={!editMode} onClick={handleRecompute}>
              Recompute entitlements
            </button>
            {currentSnapshot ? (
              <div className="stack">
                <h4>Current snapshot</h4>
                <div className="muted">
                  Version {currentSnapshot.version} • {new Date(currentSnapshot.computed_at).toLocaleString()}
                </div>
                <pre>{formatJson(currentSnapshot.entitlements)}</pre>
              </div>
            ) : (
              <div className="muted">Нет snapshot.</div>
            )}
            {previousSnapshots.length > 0 && (
              <div className="stack">
                <h4>Previous snapshots</h4>
                {previousSnapshots.map((snapshot, index) => (
                  <div key={snapshot.hash} className="card">
                    <div className="muted">
                      Version {snapshot.version} • {new Date(snapshot.computed_at).toLocaleString()}
                    </div>
                    <details>
                      <summary>Snapshot JSON</summary>
                      <pre>{formatJson(snapshot.entitlements)}</pre>
                    </details>
                    <details>
                      <summary>Diff to newer snapshot</summary>
                      {diffs[index].length === 0 ? (
                        <div className="muted">Без изменений.</div>
                      ) : (
                        <ul>
                          {diffs[index].map((entry) => (
                            <li key={`${snapshot.hash}-${entry.path}`}>
                              <strong>{entry.path}</strong>: {formatJson(entry.before)} →{" "}
                              {formatJson(entry.after)}
                            </li>
                          ))}
                        </ul>
                      )}
                    </details>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card stack">
            <h3>Effective entitlements summary</h3>
            <div>
              Snapshot hash: {state.entitlements_snapshot?.hash ?? "—"} • computed{" "}
              {state.entitlements_snapshot?.computed_at
                ? new Date(state.entitlements_snapshot.computed_at).toLocaleString()
                : "—"}
            </div>
            <div>Overrides active: {overridesByKey.size}</div>
          </div>
        </>
      )}
    </div>
  );
};

export default CommercialOrgPage;
