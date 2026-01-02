import { useCallback, useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import { Table } from "../components/common/Table";
import type { Column } from "../components/common/Table";
import { AppForbiddenState } from "../components/states";
import { FleetUnavailableState } from "../components/FleetUnavailableState";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";
import type { FleetEmployee } from "../types/fleet";
import { disableEmployee, inviteEmployee, listEmployees } from "../api/fleet";
import { ApiError } from "../api/http";
import { formatDateTime } from "../utils/format";
import { canManageFleetEmployees } from "../utils/fleetPermissions";

export function FleetEmployeesPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const { toast, showToast } = useToast();
  const [employees, setEmployees] = useState<FleetEmployee[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isForbidden, setIsForbidden] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [email, setEmail] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const canManage = canManageFleetEmployees(user);

  const loadEmployees = useCallback(async () => {
    if (!user?.token) return;
    setLoading(true);
    setError(null);
    setIsForbidden(false);
    setUnavailable(false);
    try {
      const response = await listEmployees(user.token);
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      setEmployees(response.items);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setIsForbidden(true);
        return;
      }
      setError(err instanceof Error ? err.message : t("fleet.errors.loadFailed"));
    } finally {
      setLoading(false);
    }
  }, [t, user?.token]);

  useEffect(() => {
    void loadEmployees();
  }, [loadEmployees]);

  const handleInvite = () => {
    setEmail("");
    setFormError(null);
    setShowInviteModal(true);
  };

  const handleSubmitInvite = async () => {
    if (!user?.token) return;
    if (!email.trim()) {
      setFormError(t("fleet.employees.emailRequired"));
      return;
    }
    setFormError(null);
    try {
      const response = await inviteEmployee(user.token, { email: email.trim() });
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      if (response.item) {
        setEmployees((prev) => [response.item!, ...prev]);
        showToast({ kind: "success", text: t("fleet.employees.invited") });
        setShowInviteModal(false);
      }
    } catch (err) {
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleet.errors.actionFailed") });
    }
  };

  const handleDisable = async (employee: FleetEmployee) => {
    if (!user?.token) return;
    try {
      const response = await disableEmployee(user.token, employee.id);
      if (response.unavailable) {
        setUnavailable(true);
        return;
      }
      if (response.item) {
        setEmployees((prev) => prev.map((item) => (item.id === employee.id ? response.item! : item)));
      }
      showToast({ kind: "success", text: t("fleet.employees.disabled") });
    } catch (err) {
      showToast({ kind: "error", text: err instanceof Error ? err.message : t("fleet.errors.actionFailed") });
    }
  };

  const columns: Column<FleetEmployee>[] = [
    { key: "email", title: t("fleet.employees.email"), render: (row) => row.email },
    {
      key: "status",
      title: t("fleet.employees.status"),
      render: (row) => (
        <div>
          <div>{row.status ?? t("common.notAvailable")}</div>
          {row.status === "INVITED" ? <div className="muted small">{t("fleet.employees.pending")}</div> : null}
        </div>
      ),
    },
    {
      key: "created",
      title: t("fleet.employees.created"),
      render: (row) => (row.created_at ? formatDateTime(row.created_at) : t("common.notAvailable")),
    },
    {
      key: "actions",
      title: t("fleet.employees.actions"),
      render: (row) =>
        canManage ? (
          <button type="button" className="ghost" onClick={() => void handleDisable(row)}>
            {t("fleet.employees.disable")}
          </button>
        ) : (
          <span className="muted">{t("fleet.employees.disableRestricted")}</span>
        ),
    },
  ];

  if (loading) {
    return (
      <div className="page">
        <div className="page-header">
          <h1>{t("fleet.employees.title")}</h1>
        </div>
        <Table columns={columns} data={[]} loading />
      </div>
    );
  }

  if (isForbidden) {
    return <AppForbiddenState message={t("fleet.errors.noPermission")} />;
  }

  if (unavailable) {
    return <FleetUnavailableState />;
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>{t("fleet.employees.title")}</h1>
        <div className="actions">
          {canManage ? (
            <button type="button" className="primary" onClick={handleInvite}>
              {t("fleet.employees.invite")}
            </button>
          ) : null}
          <button type="button" className="secondary" onClick={() => void loadEmployees()}>
            {t("actions.refresh")}
          </button>
        </div>
      </div>
      {error ? <div className="card state">{error}</div> : null}
      <Table
        columns={columns}
        data={employees}
        emptyState={{ title: t("fleet.employees.emptyTitle"), description: t("fleet.employees.emptyDescription") }}
      />
      {showInviteModal ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-card">
            <h2>{t("fleet.employees.inviteTitle")}</h2>
            <div className="form-grid">
              <label className="form-field">
                <span>{t("fleet.employees.email")}</span>
                <input value={email} onChange={(event) => setEmail(event.target.value)} placeholder="name@company.ru" />
              </label>
            </div>
            {formError ? <div className="error-text">{formError}</div> : null}
            <div className="actions">
              <button type="button" className="ghost" onClick={() => setShowInviteModal(false)}>
                {t("actions.comeBackLater")}
              </button>
              <button type="button" className="primary" onClick={() => void handleSubmitInvite()}>
                {t("fleet.employees.submit")}
              </button>
            </div>
          </div>
        </div>
      ) : null}
      <Toast toast={toast} />
    </div>
  );
}
