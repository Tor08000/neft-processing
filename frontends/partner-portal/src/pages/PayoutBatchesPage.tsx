import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchPayoutBatches, type PayoutBatch } from "../api/partner";
import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/StatusBadge";

export function PayoutBatchesPage() {
  const { user } = useAuth();
  const [batches, setBatches] = useState<PayoutBatch[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    if (!user) return;
    setIsLoading(true);
    fetchPayoutBatches(user.token)
      .then((data) => {
        if (active) {
          setBatches(data.items ?? []);
        }
      })
      .catch((err) => {
        console.error(err);
        if (active) {
          setError("Не удалось загрузить payout batches");
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
          <h2>Payout batches</h2>
          <Link className="ghost" to="/payouts">
            Назад к settlements
          </Link>
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
        ) : batches.length === 0 ? (
          <div className="empty-state">
            <strong>Батчи не найдены</strong>
            <span className="muted">Экспорт появится после формирования выплат.</span>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Batch ID</th>
                <th>Статус</th>
                <th>Экспорт</th>
                <th>Checksum</th>
                <th>Audit</th>
              </tr>
            </thead>
            <tbody>
              {batches.map((batch) => (
                <tr key={batch.id}>
                  <td>{batch.id}</td>
                  <td>
                    <StatusBadge status={batch.status} />
                  </td>
                  <td>
                    {batch.exportFiles && batch.exportFiles.length ? (
                      <ul className="bullets">
                        {batch.exportFiles.map((file) => (
                          <li key={file.id}>
                            {file.url ? (
                              <a className="link-button" href={file.url} target="_blank" rel="noreferrer">
                                {file.name}
                              </a>
                            ) : (
                              <span>{file.name}</span>
                            )}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <span className="muted">нет файлов</span>
                    )}
                  </td>
                  <td>{batch.checksum ?? "—"}</td>
                  <td>{batch.auditSummary ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
