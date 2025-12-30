import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchDocumentDetail, type PartnerDocumentDetail } from "../api/partner";
import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/StatusBadge";
import { SupportRequestModal } from "../components/SupportRequestModal";
import { formatCurrency, formatDateTime } from "../utils/format";

export function DocumentDetailsPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const [document, setDocument] = useState<PartnerDocumentDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isSupportOpen, setIsSupportOpen] = useState(false);

  useEffect(() => {
    let active = true;
    if (!user || !id) return;
    setIsLoading(true);
    fetchDocumentDetail(user.token, id)
      .then((data) => {
        if (active) {
          setDocument(data);
        }
      })
      .catch((err) => {
        console.error(err);
        if (active) {
          setError("Не удалось загрузить документ");
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

  if (!document) {
    return (
      <div className="empty-state empty-state--full">
        <h2>Документ не найден</h2>
        <Link className="ghost" to="/documents">
          Вернуться к списку
        </Link>
      </div>
    );
  }

  return (
    <div className="stack">
      <section className="card">
        <div className="section-title">
          <h2>{document.type}</h2>
          <div className="actions">
            <button type="button" className="secondary" onClick={() => setIsSupportOpen(true)}>
              Создать обращение
            </button>
            <Link className="ghost" to="/documents">
              Назад
            </Link>
          </div>
        </div>
        <div className="meta-grid">
          <div>
            <div className="label">Период</div>
            <div>{document.period}</div>
          </div>
          <div>
            <div className="label">Сумма</div>
            <div>{formatCurrency(document.amount ?? null)}</div>
          </div>
          <div>
            <div className="label">Статус</div>
            <StatusBadge status={document.status} />
          </div>
          <div>
            <div className="label">Подпись</div>
            <div>{document.signatureStatus ?? "—"}</div>
          </div>
          <div>
            <div className="label">ЭДО</div>
            <div>{document.edoStatus ?? "—"}</div>
          </div>
        </div>
      </section>

      <section className="card">
        <h3>Файлы</h3>
        {document.files && document.files.length ? (
          <ul className="bullets">
            {document.files.map((file) => (
              <li key={file.id}>
                {file.url ? (
                  <a className="link-button" href={file.url} target="_blank" rel="noreferrer">
                    {file.name}
                  </a>
                ) : (
                  file.name
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Файлы не приложены.</p>
        )}
      </section>

      <section className="card">
        <h3>История подписей</h3>
        {document.signatures && document.signatures.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Подписант</th>
                <th>Статус</th>
                <th>Дата</th>
              </tr>
            </thead>
            <tbody>
              {document.signatures.map((signature, index) => (
                <tr key={`${signature.signer}-${index}`}>
                  <td>{signature.signer}</td>
                  <td>{signature.status}</td>
                  <td>{formatDateTime(signature.signedAt ?? null)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">Подписи отсутствуют.</p>
        )}
      </section>

      <section className="card">
        <h3>EDO timeline</h3>
        {document.edoEvents && document.edoEvents.length ? (
          <div className="timeline">
            <div className="timeline-list">
              {document.edoEvents.map((event) => (
                <div className="timeline-item" key={event.id}>
                  <div className="timeline-item__meta">
                    <strong>{event.status}</strong>
                    <span className="muted">{formatDateTime(event.timestamp)}</span>
                  </div>
                  {event.description ? <div>{event.description}</div> : null}
                </div>
              ))}
            </div>
          </div>
        ) : (
          <p className="muted">История ЭДО пока недоступна.</p>
        )}
      </section>

      <SupportRequestModal
        isOpen={isSupportOpen}
        onClose={() => setIsSupportOpen(false)}
        subjectType="DOCUMENT"
        subjectId={document.id}
        defaultTitle={`Проблема с документом ${document.id}`}
      />
    </div>
  );
}
