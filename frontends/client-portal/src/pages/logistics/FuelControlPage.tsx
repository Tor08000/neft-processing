import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../../auth/AuthContext";
import { fetchFuelAlerts, fetchFuelReport, fetchUnlinkedFuel, runFuelLinker } from "../../api/logistics";

export function FuelControlPage() {
  const { user } = useAuth();
  const [tab, setTab] = useState<"unlinked" | "alerts" | "reports">("unlinked");
  const [from, setFrom] = useState(() => new Date(Date.now() - 7 * 86400000).toISOString());
  const [to, setTo] = useState(() => new Date().toISOString());
  const [unlinked, setUnlinked] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [reports, setReports] = useState<any[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  const token = user?.token;

  useEffect(() => {
    if (!token) return;
    if (tab === "unlinked") {
      fetchUnlinkedFuel(token, { date_from: from, date_to: to, limit: 100, offset: 0 }).then(setUnlinked).catch(() => setUnlinked([]));
    }
    if (tab === "alerts") {
      fetchFuelAlerts(token, { date_from: from, date_to: to, status: "OPEN", limit: 100, offset: 0 }).then(setAlerts).catch(() => setAlerts([]));
    }
    if (tab === "reports") {
      fetchFuelReport(token, { date_from: from, date_to: to, group_by: "trip", period: "day" }).then(setReports).catch(() => setReports([]));
    }
  }, [tab, token, from, to]);

  const canRun = useMemo(() => Boolean(token), [token]);

  return (
    <section className="stack gap-16" aria-label="fuel-control-page">
      <header className="stack gap-8">
        <h1>Fuel Control</h1>
        <div className="row gap-8 wrap">
          <input aria-label="date-from" value={from} onChange={(e) => setFrom(e.target.value)} />
          <input aria-label="date-to" value={to} onChange={(e) => setTo(e.target.value)} />
          <button
            type="button"
            disabled={!canRun}
            onClick={async () => {
              if (!token) return;
              const result = await runFuelLinker(token, { date_from: from, date_to: to });
              setMessage(`processed:${result.processed}`);
            }}
          >
            Запустить привязку
          </button>
          {message ? <span>{message}</span> : null}
        </div>
      </header>

      <div className="tabs">
        <button type="button" className={tab === "unlinked" ? "secondary" : "ghost"} onClick={() => setTab("unlinked")}>Unlinked</button>
        <button type="button" className={tab === "alerts" ? "secondary" : "ghost"} onClick={() => setTab("alerts")}>Alerts</button>
        <button type="button" className={tab === "reports" ? "secondary" : "ghost"} onClick={() => setTab("reports")}>Reports</button>
      </div>

      {tab === "unlinked" ? (
        <table><tbody>{unlinked.map((row) => <tr key={row.fuel_tx_id}><td>{row.station ?? "-"}</td><td>{row.best_score}</td></tr>)}</tbody></table>
      ) : null}
      {tab === "alerts" ? (
        <table><tbody>{alerts.map((row) => <tr key={row.id}><td>{row.type}</td><td>{row.severity}</td><td>{row.title}</td></tr>)}</tbody></table>
      ) : null}
      {tab === "reports" ? (
        <table><tbody>{reports.map((row) => <tr key={row.group}><td>{row.group}</td><td>{row.liters}</td><td>{row.amount}</td></tr>)}</tbody></table>
      ) : null}
    </section>
  );
}
