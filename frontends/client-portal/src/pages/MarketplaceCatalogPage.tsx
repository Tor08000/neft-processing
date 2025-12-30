import { type ChangeEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ShoppingCart } from "../components/icons";
import { fetchMarketplaceCatalog } from "../api/marketplace";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { EmptyState } from "../components/EmptyState";
import { AppErrorState, AppForbiddenState } from "../components/states";
import type { MarketplaceCatalogItem } from "../types/marketplace";
import { formatMoney } from "../utils/format";
import { useI18n } from "../i18n";

interface CatalogErrorState {
  message: string;
  status?: number;
  correlationId?: string | null;
}

export function MarketplaceCatalogPage() {
  const { user } = useAuth();
  const { t } = useI18n();
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
        setError({ message: err instanceof Error ? err.message : t("marketplaceCatalog.errors.loadFailed") });
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

  if (!user) {
    return <AppForbiddenState message={t("marketplaceCatalog.forbidden.clientOnly")} />;
  }

  if (error?.status === 403) {
    return <AppForbiddenState message={t("marketplaceCatalog.forbidden.catalogDenied")} />;
  }

  return (
    <div className="stack">
      <div className="card">
        <div className="card__header">
          <div>
            <h2>{t("marketplaceCatalog.title")}</h2>
            <p className="muted">{t("marketplaceCatalog.subtitle")}</p>
          </div>
        </div>

        <div className="filters">
          <div className="filter">
            <label htmlFor="category">{t("marketplaceCatalog.filters.category")}</label>
            <input id="category" name="category" value={filters.category} onChange={handleFilterChange} />
          </div>
          <div className="filter">
            <label htmlFor="partner">{t("marketplaceCatalog.filters.partner")}</label>
            <input id="partner" name="partner" value={filters.partner} onChange={handleFilterChange} />
          </div>
          <div className="filter">
            <label htmlFor="location">{t("marketplaceCatalog.filters.location")}</label>
            <input id="location" name="location" value={filters.location} onChange={handleFilterChange} />
          </div>
          <div className="filter">
            <label htmlFor="priceFrom">{t("marketplaceCatalog.filters.priceFrom")}</label>
            <input id="priceFrom" name="priceFrom" value={filters.priceFrom} onChange={handleFilterChange} />
          </div>
          <div className="filter">
            <label htmlFor="priceTo">{t("marketplaceCatalog.filters.priceTo")}</label>
            <input id="priceTo" name="priceTo" value={filters.priceTo} onChange={handleFilterChange} />
          </div>
          <div className="filter">
            <label htmlFor="availability">{t("marketplaceCatalog.filters.availability")}</label>
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
        <EmptyState
          icon={<ShoppingCart />}
          title={t("emptyStates.marketplaceCatalog.title")}
          description={t("emptyStates.marketplaceCatalog.description")}
          primaryAction={{
            label: t("actions.refresh"),
            onClick: loadCatalog,
          }}
          secondaryAction={{
            label: t("actions.comeBackLater"),
            to: "/dashboard",
          }}
        />
      ) : null}

      {!isLoading && !error && items.length > 0 ? (
        <div className="grid two">
          {items.map((item) => (
            <div className="card" key={item.id}>
                <div className="stack">
                  <div>
                    <h3>{item.title}</h3>
                    <div className="muted small">{item.category ?? t("marketplaceCatalog.card.categoryFallback")}</div>
                  </div>
                  <div className="muted">
                    {item.description ?? t("marketplaceCatalog.card.descriptionFallback")}
                  </div>
                  <div className="stack">
                    <div>
                      {t("marketplaceCatalog.card.partner", { name: item.partner_name ?? t("common.notAvailable") })}
                    </div>
                    <div>
                      {t("marketplaceCatalog.card.priceFrom", {
                        price:
                          item.price_from !== undefined && item.price_from !== null
                            ? formatMoney(item.price_from, item.currency ?? "RUB")
                            : t("common.notAvailable"),
                      })}
                    </div>
                    <div>
                      {t("marketplaceCatalog.card.availability", {
                        availability: item.availability ?? t("common.notAvailable"),
                      })}
                    </div>
                  </div>
                  <div className="actions">
                    <Link to={`/marketplace/${item.id}`} className="link-button">
                      {t("common.open")}
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
