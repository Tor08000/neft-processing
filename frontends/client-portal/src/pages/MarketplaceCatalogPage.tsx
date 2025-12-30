import { type ChangeEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchMarketplaceCatalog } from "../api/marketplace";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { AppEmptyState, AppErrorState, AppForbiddenState } from "../components/states";
import type { MarketplaceCatalogItem } from "../types/marketplace";
import { formatMoney } from "../utils/format";

interface CatalogErrorState {
  message: string;
  status?: number;
  correlationId?: string | null;
}

export function MarketplaceCatalogPage() {
  const { user } = useAuth();
  const [items, setItems] = useState<MarketplaceCatalogItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<CatalogErrorState | null>(null);
  const [filters, setFilters] = useState({
    category: "",
    partner: "",
    location: "",
    priceFrom: "",
    priceTo: "",
    availability: "",
  });

  const loadCatalog = () => {
    if (!user) return;
    setIsLoading(true);
    setError(null);
    fetchMarketplaceCatalog(user, filters)
      .then((resp) => setItems(resp.items ?? []))
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setError({ message: err.message, status: err.status, correlationId: err.correlationId });
          return;
        }
        setError({ message: err instanceof Error ? err.message : "Не удалось загрузить услуги" });
      })
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    loadCatalog();
  }, [user, filters]);

  const handleFilterChange = (evt: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = evt.target;
    setFilters((prev) => ({ ...prev, [name]: value }));
  };

  const handleReset = () => {
    setFilters({
      category: "",
      partner: "",
      location: "",
      priceFrom: "",
      priceTo: "",
      availability: "",
    });
  };

  const hasFilters = useMemo(
    () => Object.values(filters).some((value) => value.trim().length > 0),
    [filters],
  );

  if (!user) {
    return <AppForbiddenState message="Доступ к маркетплейсу доступен только клиентам." />;
  }

  if (error?.status === 403) {
    return <AppForbiddenState message="Доступ к каталогу услуг запрещён." />;
  }

  return (
    <div className="stack">
      <div className="card">
        <div className="card__header">
          <div>
            <h2>Marketplace</h2>
            <p className="muted">Выбирайте услуги партнёров и оформляйте заказы онлайн.</p>
          </div>
        </div>

        <div className="filters">
          <div className="filter">
            <label htmlFor="category">Категория</label>
            <input id="category" name="category" value={filters.category} onChange={handleFilterChange} />
          </div>
          <div className="filter">
            <label htmlFor="partner">Партнёр</label>
            <input id="partner" name="partner" value={filters.partner} onChange={handleFilterChange} />
          </div>
          <div className="filter">
            <label htmlFor="location">Станция / Локация</label>
            <input id="location" name="location" value={filters.location} onChange={handleFilterChange} />
          </div>
          <div className="filter">
            <label htmlFor="priceFrom">Цена от</label>
            <input id="priceFrom" name="priceFrom" value={filters.priceFrom} onChange={handleFilterChange} />
          </div>
          <div className="filter">
            <label htmlFor="priceTo">Цена до</label>
            <input id="priceTo" name="priceTo" value={filters.priceTo} onChange={handleFilterChange} />
          </div>
          <div className="filter">
            <label htmlFor="availability">Доступность</label>
            <input id="availability" name="availability" value={filters.availability} onChange={handleFilterChange} />
          </div>
        </div>
      </div>

      {isLoading ? (
        <div className="card">
          <div className="skeleton-stack">
            <div className="skeleton-line" />
            <div className="skeleton-line" />
            <div className="skeleton-line" />
          </div>
        </div>
      ) : null}

      {error ? (
        <AppErrorState message={error.message} status={error.status} correlationId={error.correlationId} onRetry={loadCatalog} />
      ) : null}

      {!isLoading && !error && items.length === 0 ? (
        <AppEmptyState
          title="Услуги не найдены"
          description="Попробуйте изменить фильтры или сбросить поиск."
          action={
            hasFilters ? (
              <button type="button" className="secondary" onClick={handleReset}>
                Сбросить фильтры
              </button>
            ) : null
          }
        />
      ) : null}

      {!isLoading && !error && items.length > 0 ? (
        <div className="grid two">
          {items.map((item) => (
            <div className="card" key={item.id}>
              <div className="stack">
                <div>
                  <h3>{item.title}</h3>
                  <div className="muted small">{item.category ?? "Категория не указана"}</div>
                </div>
                <div className="muted">{item.description ?? "Описание услуги не предоставлено."}</div>
                <div className="stack">
                  <div>Партнёр: {item.partner_name ?? "—"}</div>
                  <div>
                    Цена от:{" "}
                    {item.price_from !== undefined && item.price_from !== null
                      ? formatMoney(item.price_from, item.currency ?? "RUB")
                      : "—"}
                  </div>
                  <div>Доступность: {item.availability ?? "—"}</div>
                </div>
                <div className="actions">
                  <Link to={`/marketplace/${item.id}`} className="link-button">
                    Открыть
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
