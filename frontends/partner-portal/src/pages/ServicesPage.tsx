import { useEffect, useState } from "react";
import { fetchServices, type ServiceCatalogItem } from "../api/partner";
import { useAuth } from "../auth/AuthContext";
import { StatusBadge } from "../components/StatusBadge";
import { formatCurrency } from "../utils/format";

export function ServicesPage() {
  const { user } = useAuth();
  const [services, setServices] = useState<ServiceCatalogItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    if (!user) return;
    setIsLoading(true);
    fetchServices(user.token)
      .then((data) => {
        if (active) {
          setServices(data.items ?? []);
        }
      })
      .catch((err) => {
        console.error(err);
        if (active) {
          setError("Не удалось загрузить каталог сервисов");
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
          <h2>Каталог сервисов</h2>
          <span className="muted">Marketplace v1 (read-only)</span>
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
        ) : services.length === 0 ? (
          <div className="empty-state">
            <strong>Каталог пуст</strong>
            <span className="muted">Услуги появятся после подключения marketplace.</span>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Услуга</th>
                <th>Статус</th>
                <th>Цена</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {services.map((service) => (
                <tr key={service.id}>
                  <td>{service.name}</td>
                  <td>
                    <StatusBadge status={service.status} />
                  </td>
                  <td>{formatCurrency(service.price ?? null)}</td>
                  <td>
                    <button type="button" className="secondary" disabled title="Будет доступно в v2">
                      Edit
                    </button>
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
