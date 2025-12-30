import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchDocuments, type PartnerDocumentListItem } from "../api/partner";
import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/StatusBadge";
import { formatCurrency } from "../utils/format";

export function DocumentsPage() {
  const { user } = useAuth();
  const [documents, setDocuments] = useState<PartnerDocumentListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    if (!user) return;
    setIsLoading(true);
    fetchDocuments(user.token)
      .then((data) => {
        if (active) {
          setDocuments(data.items ?? []);
        }
      })
      .catch((err) => {
        console.error(err);
        if (active) {
          setError("Не удалось загрузить документы");
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
          <h2>Документы</h2>
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
        ) : documents.length === 0 ? (
          <div className="empty-state">
            <strong>Документы отсутствуют</strong>
            <span className="muted">Здесь появятся акты и сверки по выплатам.</span>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Тип</th>
                <th>Период</th>
                <th>Сумма</th>
                <th>Статус</th>
                <th>Подпись</th>
                <th>ЭДО</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.id}>
                  <td>{doc.type}</td>
                  <td>{doc.period}</td>
                  <td>{formatCurrency(doc.amount ?? null)}</td>
                  <td>
                    <StatusBadge status={doc.status} />
                  </td>
                  <td>{doc.signatureStatus ?? "—"}</td>
                  <td>{doc.edoStatus ?? "—"}</td>
                  <td>
                    <Link className="ghost" to={`/documents/${doc.id}`}>
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
