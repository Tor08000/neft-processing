import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchStations, type StationListItem } from "../api/partner";
import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/StatusBadge";
import { formatNumber } from "../utils/format";

export function StationsPage() {
  const { user } = useAuth();
  const [stations, setStations] = useState<StationListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    if (!user) return;
    setIsLoading(true);
    fetchStations(user.token)
      .then((data) => {
        if (active) {
          setStations(data.items ?? []);
        }
      })
      .catch((err) => {
        console.error(err);
        if (active) {
          setError("Не удалось загрузить список АЗС");
        }
      })
      .finally(() => {
        if (active) {
          setIsLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [user]);

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <h2>АЗС партнёра</h2>
          <span className="muted">Всего: {stations.length}</span>
        </div>

        {isLoading ? (
          <div className="skeleton-stack" aria-busy="true">
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        ) : error ? (
          <div className="error" role="alert">
            {error}
          </div>
        ) : stations.length === 0 ? (
          <div className="empty-state">
            <strong>Станции не найдены</strong>
            <span className="muted">Данные появятся после подключения точек.</span>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Станция</th>
                <th>Адрес</th>
                <th>Статус</th>
                <th>Онлайн</th>
                <th>Операции</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {stations.map((station) => (
                <tr key={station.id}>
                  <td>
                    <div>{station.name}</div>
                    <div className="muted small">{station.code ?? "—"}</div>
                  </td>
                  <td>{station.address}</td>
                  <td>
                    <StatusBadge status={station.status} />
                  </td>
                  <td>
                    {station.onlineStatus ? <StatusBadge status={station.onlineStatus} /> : "—"}
                  </td>
                  <td>{formatNumber(station.transactionsCount ?? null)}</td>
                  <td>
                    <Link className="ghost" to={`/stations/${station.id}`}>
                      details
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
