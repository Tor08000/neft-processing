import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchMarketplaceService } from "../api/marketplace";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { AppEmptyState, AppErrorState, AppForbiddenState } from "../components/states";
import type { MarketplaceServiceDetails } from "../types/marketplace";
import { formatMoney } from "../utils/format";
import { CreateMarketplaceOrderModal } from "../components/CreateMarketplaceOrderModal";

interface ServiceErrorState {
  message: string;
  status?: number;
  correlationId?: string | null;
}

export function MarketplaceServicePage() {
  const { serviceId } = useParams<{ serviceId: string }>();
  const { user } = useAuth();
  const [service, setService] = useState<MarketplaceServiceDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<ServiceErrorState | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const loadService = () => {
    if (!user || !serviceId) return;
    setIsLoading(true);
    setError(null);
    fetchMarketplaceService(user, serviceId)
      .then((resp) => setService(resp))
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setError({ message: err.message, status: err.status, correlationId: err.correlationId });
          return;
        }
        setError({ message: err instanceof Error ? err.message : "Не удалось загрузить услугу" });
      })
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    loadService();
  }, [user, serviceId]);

  if (!user) {
    return <AppForbiddenState message="Нет доступа к карточке услуги." />;
  }

  if (error?.status === 403) {
    return <AppForbiddenState message="Просмотр услуги запрещён." />;
  }

  return (
    <div className="stack">
      <div className="card">
        <div className="card__header">
          <div>
            <h2>Карточка услуги</h2>
            <p className="muted">Подробности услуги и доступные предложения.</p>
          </div>
          <Link to="/marketplace" className="link-button">
            Назад в каталог
          </Link>
        </div>

        {isLoading ? (
          <div className="skeleton-stack">
            <div className="skeleton-line" />
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        ) : null}

        {error ? (
          <AppErrorState message={error.message} status={error.status} correlationId={error.correlationId} onRetry={loadService} />
        ) : null}

        {!isLoading && !error && service ? (
          <div className="stack">
            <div>
              <h3>{service.title}</h3>
              <div className="muted small">{service.category ?? "Категория не указана"}</div>
            </div>
            <div className="muted">{service.description ?? "Описание услуги отсутствует."}</div>

            <div className="card muted-card">
              <div className="muted small">Партнёр</div>
              {service.partner?.url ? (
                <a href={service.partner.url} target="_blank" rel="noreferrer">
                  {service.partner.name ?? service.partner.id ?? "Партнёр"}
                </a>
              ) : (
                <Link to={`/marketplace?partner=${service.partner?.id ?? ""}`}>
                  {service.partner?.name ?? service.partner?.id ?? "Партнёр не указан"}
                </Link>
              )}
            </div>

            <div>
              <div className="section-title">
                <h3>Доступные офферы</h3>
                <button
                  type="button"
                  className="primary"
                  onClick={() => setIsModalOpen(true)}
                  disabled={!service.offers || service.offers.length === 0}
                >
                  Заказать услугу
                </button>
              </div>

              {service.offers && service.offers.length > 0 ? (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Цена</th>
                      <th>Локация</th>
                      <th>Доступность</th>
                      <th>Условия</th>
                      <th>Документы</th>
                    </tr>
                  </thead>
                  <tbody>
                    {service.offers.map((offer) => (
                      <tr key={offer.id}>
                        <td>
                          {offer.price !== undefined && offer.price !== null
                            ? formatMoney(offer.price, offer.currency ?? "RUB")
                            : "Цена по запросу"}
                        </td>
                        <td>{offer.location_name ?? "—"}</td>
                        <td>{offer.availability ?? "—"}</td>
                        <td>{offer.conditions ?? "—"}</td>
                        <td>{offer.documents?.length ? offer.documents.join(", ") : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <AppEmptyState title="Офферы не найдены" description="Партнёр пока не добавил предложения." />
              )}
            </div>

            <div className="stack">
              <div>
                <div className="muted small">Документы и условия</div>
                <div>{service.terms ?? "Условия не предоставлены."}</div>
              </div>
              {service.documents && service.documents.length > 0 ? (
                <ul className="pill-list">
                  {service.documents.map((doc) => (
                    <li className="pill" key={doc}>
                      {doc}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>

      {!isLoading && !error && !service ? (
        <AppEmptyState title="Услуга не найдена" description="Попробуйте вернуться в каталог." />
      ) : null}

      {service && isModalOpen && service.offers ? (
        <CreateMarketplaceOrderModal
          serviceId={service.id}
          serviceTitle={service.title}
          offers={service.offers}
          onClose={() => setIsModalOpen(false)}
        />
      ) : null}
    </div>
  );
}
