import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { AppForbiddenState, AppErrorState } from "../components/states";
import { fetchServiceSloBreaches, fetchServiceSlos } from "../api/slo";
import type { ServiceSloBreachItem, ServiceSloItem, ServiceSloService, ServiceSloWindow } from "../types/slo";
import { formatDateTime } from "../utils/format";
import { hasAnyRole } from "../utils/roles";

const serviceLabels: Record<ServiceSloService, string> = {
  exports: "Exports",
  email: "Email",
  support: "Support",
  schedules: "Scheduled Reports",
};

const metricLabels: Record<string, string> = {
  latency: "Latency",
  success_rate: "Success rate",
};

const windowLabels: Record<ServiceSloWindow, string> = {
  "7d": "7d",
  "30d": "30d",
};

const statusBadge = (status?: string | null) => {
  if (!status) return { label: "OK", className: "pill pill--success" };
  if (status === "OPEN") return { label: "OPEN", className: "pill pill--danger" };
  if (status === "ACKED") return { label: "ACKED", className: "pill pill--warning" };
  return { label: status, className: "pill" };
};

export function ServiceSloPage() {
  const { user } = useAuth();
  const canAccess = useMemo(() => hasAnyRole(user, ["CLIENT_OWNER", "CLIENT_ADMIN"]), [user]);
  const [slos, setSlos] = useState<ServiceSloItem[]>([]);
  const [breaches, setBreaches] = useState<ServiceSloBreachItem[]>([]);
  const [filters, setFilters] = useState<{ service: ServiceSloService | ""; window: ServiceSloWindow | "" }>({
    service: "",
    window: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user || !canAccess) return;
    let mounted = true;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [sloResponse, breachResponse] = await Promise.all([
          fetchServiceSlos(user),
          fetchServiceSloBreaches(user, {
            service: filters.service || undefined,
            window: filters.window || undefined,
          }),
        ]);
        if (!mounted) return;
        setSlos(sloResponse.items ?? []);
        setBreaches(breachResponse.items ?? []);
      } catch (err) {
        if (!mounted) return;
        if (err instanceof Error) {
          setError(err.message || "Не удалось загрузить SLO");
        } else {
          setError("Не удалось загрузить SLO");
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };
    void load();
    return () => {
      mounted = false;
    };
  }, [user, canAccess, filters]);

  if (!user) {
    return <AppForbiddenState message="Требуется авторизация" />;
  }

  if (!canAccess) {
    return <AppForbiddenState message="Недостаточно прав для просмотра SLO" />;
  }

  if (error) {
    return <AppErrorState message={error} />;
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="card__header">
          <div>
            <h2>SLO / SLA</h2>
            <p className="muted">Отслеживайте целевые показатели качества по сервисам.</p>
          </div>
          <div className="stack-inline">
            <label className="stack-inline">
              <span className="muted">Service</span>
              <select
                value={filters.service}
                onChange={(event) =>
                  setFilters((prev) => ({ ...prev, service: event.target.value as ServiceSloService | "" }))
                }
              >
                <option value="">Все</option>
                {Object.entries(serviceLabels).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="stack-inline">
              <span className="muted">Window</span>
              <select
                value={filters.window}
                onChange={(event) =>
                  setFilters((prev) => ({ ...prev, window: event.target.value as ServiceSloWindow | "" }))
                }
              >
                <option value="">Все</option>
                {Object.entries(windowLabels).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
      </section>

      <section className="card">
        <div className="card__header">
          <div>
            <h3>Активные SLO</h3>
            <p className="muted">Список целей и текущий статус окна.</p>
          </div>
        </div>
        {loading ? (
          <div className="muted">Загрузка…</div>
        ) : (
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>Service</th>
                  <th>Metric</th>
                  <th>Objective</th>
                  <th>Window</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {slos.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="muted">
                      Нет данных
                    </td>
                  </tr>
                ) : (
                  slos.map((item) => {
                    const badge = statusBadge(item.breach_status ?? null);
                    return (
                      <tr key={item.id}>
                        <td>{serviceLabels[item.service] ?? item.service}</td>
                        <td>{metricLabels[item.metric] ?? item.metric}</td>
                        <td>{item.objective ?? "—"}</td>
                        <td>{item.window}</td>
                        <td>
                          <span className={badge.className}>{badge.label}</span>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card">
        <div className="card__header">
          <div>
            <h3>Breach history</h3>
            <p className="muted">Нарушения SLO по выбранным фильтрам.</p>
          </div>
        </div>
        {loading ? (
          <div className="muted">Загрузка…</div>
        ) : (
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>Service</th>
                  <th>Metric</th>
                  <th>Objective</th>
                  <th>Observed</th>
                  <th>Window</th>
                  <th>Status</th>
                  <th>Breached at</th>
                </tr>
              </thead>
              <tbody>
                {breaches.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="muted">
                      Нарушений не найдено
                    </td>
                  </tr>
                ) : (
                  breaches.map((breach, index) => {
                    const badge = statusBadge(breach.status);
                    return (
                      <tr key={`${breach.service}-${breach.metric}-${index}`}>
                        <td>{serviceLabels[breach.service] ?? breach.service}</td>
                        <td>{metricLabels[breach.metric] ?? breach.metric}</td>
                        <td>{breach.objective}</td>
                        <td>{breach.observed}</td>
                        <td>{breach.window}</td>
                        <td>
                          <span className={badge.className}>{badge.label}</span>
                        </td>
                        <td>{formatDateTime(breach.breached_at, undefined)}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
