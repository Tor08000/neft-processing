import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchStationDetail, type StationDetail } from "../api/partner";
import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/StatusBadge";
import { formatCurrency, formatDate, formatNumber } from "../utils/format";

export function StationDetailsPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [station, setStation] = useState<StationDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    if (!user || !id) return;
    setIsLoading(true);
    fetchStationDetail(user.token, id)
      .then((data) => {
        if (active) {
          setStation(data);
        }
      })
      .catch((err) => {
        console.error(err);
        if (active) {
          setError("Не удалось загрузить данные станции");
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
  }, [user, id]);

  if (isLoading) {
    return (
      <div className="card">
        <div className="skeleton-stack" aria-busy="true">
          <div className="skeleton-line" />
          <div className="skeleton-line" />
          <div className="skeleton-line" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card">
        <div className="error" role="alert">
          {error}
        </div>
      </div>
    );
  }

  if (!station) {
    return (
      <div className="empty-state empty-state--full">
        <h2>Станция не найдена</h2>
        <Link className="ghost" to="/stations">
          Вернуться к списку
        </Link>
      </div>
    );
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <div>
            <h2>{station.name}</h2>
            <div className="muted">{station.address}</div>
          </div>
          <Link className="ghost" to="/stations">
            Назад
          </Link>
        </div>
        <div className="meta-grid">
          <div>
            <div className="label">Код станции</div>
            <div>{station.code ?? "—"}</div>
          </div>
          <div>
            <div className="label">Сеть</div>
            <div>{station.network ?? "—"}</div>
          </div>
          <div>
            <div className="label">Статус</div>
            <StatusBadge status={station.status} />
          </div>
          <div>
            <div className="label">Онлайн</div>
            {station.onlineStatus ? <StatusBadge status={station.onlineStatus} /> : "—"}
          </div>
        </div>
      </section>

      <section className="card">
        <h3>Терминалы / POS</h3>
        {station.terminals && station.terminals.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Название</th>
                <th>Статус</th>
              </tr>
            </thead>
            <tbody>
              {station.terminals.map((terminal) => (
                <tr key={terminal.id}>
                  <td>{terminal.id}</td>
                  <td>{terminal.name ?? "—"}</td>
                  <td>
                    <StatusBadge status={terminal.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">Терминалы отсутствуют.</p>
        )}
      </section>

      <section className="card">
        <h3>Сводка по операциям</h3>
        {station.transactionSummary ? (
          <div className="stats-grid">
            <div className="stat">
              <div className="stat__label">Период</div>
              <div className="stat__value">{station.transactionSummary.period ?? "—"}</div>
            </div>
            <div className="stat">
              <div className="stat__label">Количество операций</div>
              <div className="stat__value">{formatNumber(station.transactionSummary.totalCount ?? null)}</div>
            </div>
            <div className="stat">
              <div className="stat__label">Сумма</div>
              <div className="stat__value">{formatCurrency(station.transactionSummary.totalAmount ?? null)}</div>
            </div>
          </div>
        ) : (
          <p className="muted">Сводка пока не доступна.</p>
        )}
      </section>

      <section className="card">
        <div className="section-title">
          <h3>Топ причин отказов</h3>
          <span className="muted">Explain доступен для ключевых отказов</span>
        </div>
        {station.declineReasons && station.declineReasons.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Причина</th>
                <th>Кол-во</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {station.declineReasons.map((reason) => (
                <tr key={reason.code}>
                  <td>
                    <div>{reason.label}</div>
                    <div className="muted small">{reason.code}</div>
                  </td>
                  <td>{formatNumber(reason.count)}</td>
                  <td>
                    {reason.explainUrl ? (
                      <a className="link-button" href={reason.explainUrl} target="_blank" rel="noreferrer">
                        Explain
                      </a>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">Данные по отказам отсутствуют.</p>
        )}
      </section>

      <section className="card">
        <div className="section-title">
          <h3>Цены</h3>
          <button className="secondary" type="button" disabled title="coming next">
            Upload/Update prices
          </button>
        </div>
        {station.prices && station.prices.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Продукт</th>
                <th>Цена</th>
                <th>Обновлено</th>
              </tr>
            </thead>
            <tbody>
              {station.prices.map((price) => (
                <tr key={price.product}>
                  <td>{price.product}</td>
                  <td>{formatCurrency(price.price)}</td>
                  <td>{formatDate(price.updatedAt ?? null)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">Прайс пока не загружен.</p>
        )}
      </section>
    </div>
  );
}
