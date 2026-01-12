import { type ChangeEvent, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ShoppingCart } from "../components/icons";
import { listMarketplaceProducts } from "../api/marketplace";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { EmptyState } from "../components/EmptyState";
import { AppErrorState, AppForbiddenState } from "../components/states";
import type { MarketplaceProductSummary } from "../types/marketplace";
import { canOrder } from "../utils/marketplacePermissions";
import { useI18n } from "../i18n";

interface CatalogErrorState {
  message: string;
  status?: number;
  correlationId?: string | null;
}

export function MarketplaceCatalogPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [items, setItems] = useState<MarketplaceProductSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<CatalogErrorState | null>(null);
  const [filters, setFilters] = useState({
    q: "",
    category: "",
    type: "",
    priceModel: "",
    partnerId: "",
    sort: "newest",
  });
  const [showAllCategories, setShowAllCategories] = useState(false);
  const canOrderProduct = canOrder(user);
  const hasActiveFilters = Boolean(
    filters.q || filters.category || filters.type || filters.priceModel || filters.partnerId,
  );

  const categories = useMemo(
    () =>
      Array.from(new Set(items.map((item) => item.category).filter((value): value is string => Boolean(value))))
        .sort((a, b) => a.localeCompare(b)),
    [items],
  );
  const partners = useMemo(() => {
    const entries = items
      .map((item) => ({ id: item.partner_id, name: item.partner_name }))
      .filter((item): item is { id: string; name: string } => Boolean(item.id && item.name));
    const unique = new Map<string, string>();
    entries.forEach((entry) => unique.set(entry.id, entry.name));
    return Array.from(unique.entries())
      .map(([id, name]) => ({ id, name }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [items]);
  const visibleCategories = showAllCategories ? categories : categories.slice(0, 6);

  const loadCatalog = () => {
    if (!user) return;
    setIsLoading(true);
    setError(null);
    listMarketplaceProducts(user, filters)
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

  const handleCategoryClick = (category: string) => {
    setFilters((prev) => ({ ...prev, category }));
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

        {categories.length ? (
          <div className="summary-chips">
            <button
              type="button"
              className={`summary-chip ${filters.category ? "" : "is-active"}`}
              onClick={() => handleCategoryClick("")}
            >
              {t("marketplaceCatalog.categories.all")}
            </button>
            {visibleCategories.map((category) => (
              <button
                key={category}
                type="button"
                className={`summary-chip ${filters.category === category ? "is-active" : ""}`}
                onClick={() => handleCategoryClick(category)}
              >
                {category}
              </button>
            ))}
            {categories.length > 6 ? (
              <button type="button" className="summary-chip" onClick={() => setShowAllCategories((prev) => !prev)}>
                {showAllCategories ? t("marketplaceCatalog.categories.less") : t("marketplaceCatalog.categories.more")}
              </button>
            ) : null}
          </div>
        ) : null}

        <div className="filters">
          <div className="filter filter--wide">
            <label htmlFor="search">{t("marketplaceCatalog.filters.search")}</label>
            <input id="search" name="q" value={filters.q} onChange={handleFilterChange} />
          </div>
          <div className="filter">
            <label htmlFor="category">{t("marketplaceCatalog.filters.category")}</label>
            <select id="category" name="category" value={filters.category} onChange={handleFilterChange}>
              <option value="">{t("marketplaceCatalog.filters.all")}</option>
              {categories.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </div>
          <div className="filter">
            <label htmlFor="type">{t("marketplaceCatalog.filters.type")}</label>
            <select id="type" name="type" value={filters.type} onChange={handleFilterChange}>
              <option value="">{t("marketplaceCatalog.filters.all")}</option>
              <option value="SERVICE">{t("marketplaceCatalog.types.service")}</option>
              <option value="PRODUCT">{t("marketplaceCatalog.types.product")}</option>
            </select>
          </div>
          <div className="filter">
            <label htmlFor="priceModel">{t("marketplaceCatalog.filters.priceModel")}</label>
            <select id="priceModel" name="priceModel" value={filters.priceModel} onChange={handleFilterChange}>
              <option value="">{t("marketplaceCatalog.filters.all")}</option>
              <option value="FIXED">{t("marketplaceCatalog.priceModels.fixed")}</option>
              <option value="PER_UNIT">{t("marketplaceCatalog.priceModels.perUnit")}</option>
              <option value="TIERED">{t("marketplaceCatalog.priceModels.tiered")}</option>
            </select>
          </div>
          <div className="filter">
            <label htmlFor="partnerId">{t("marketplaceCatalog.filters.partner")}</label>
            <select id="partnerId" name="partnerId" value={filters.partnerId} onChange={handleFilterChange}>
              <option value="">{t("marketplaceCatalog.filters.all")}</option>
              {partners.map((partner) => (
                <option key={partner.id} value={partner.id}>
                  {partner.name}
                </option>
              ))}
            </select>
          </div>
          <div className="filter">
            <label htmlFor="sort">{t("marketplaceCatalog.filters.sort")}</label>
            <select id="sort" name="sort" value={filters.sort} onChange={handleFilterChange}>
              <option value="newest">{t("marketplaceCatalog.sort.newest")}</option>
              <option value="price_asc">{t("marketplaceCatalog.sort.priceAsc")}</option>
              <option value="price_desc">{t("marketplaceCatalog.sort.priceDesc")}</option>
            </select>
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
        <AppErrorState
          message={
            error.status === 404 || error.status === 503
              ? t("marketplaceCatalog.errors.unavailable")
              : error.message
          }
          status={error.status}
          correlationId={error.correlationId}
          onRetry={loadCatalog}
        />
      ) : null}

      {!isLoading && !error && items.length === 0 ? (
        <EmptyState
          icon={<ShoppingCart />}
          title={
            hasActiveFilters ? t("marketplaceCatalog.empty.filteredTitle") : t("emptyStates.marketplaceCatalog.title")
          }
          description={
            hasActiveFilters
              ? t("marketplaceCatalog.empty.filteredDescription")
              : t("emptyStates.marketplaceCatalog.description")
          }
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
                  <div className="muted small">{item.partner_name ?? t("marketplaceCatalog.card.partnerFallback")}</div>
                </div>
                <div className="badge-row">
                  <span className="neft-chip neft-chip-muted">
                    {item.category ?? t("marketplaceCatalog.card.categoryFallback")}
                  </span>
                  <span className="neft-chip neft-chip-info">
                    {item.type === "SERVICE"
                      ? t("marketplaceCatalog.types.service")
                      : t("marketplaceCatalog.types.product")}
                  </span>
                </div>
                <div className="muted">{item.short_description ?? t("marketplaceCatalog.card.descriptionFallback")}</div>
                <div className="stack">
                  <div>
                    {t("marketplaceCatalog.card.priceSummary", {
                      price: item.price_summary ?? t("marketplaceCatalog.card.priceFallback"),
                    })}
                  </div>
                </div>
                <div className="actions">
                  <Link to={`/marketplace/products/${item.id}`} className="link-button">
                    {t("marketplaceCatalog.card.view")}
                  </Link>
                  {canOrderProduct ? (
                    <Link to={`/marketplace/products/${item.id}`} className="ghost">
                      {t("marketplaceCatalog.card.order")}
                    </Link>
                  ) : null}
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
