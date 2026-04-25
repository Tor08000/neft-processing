import { type ChangeEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { ShoppingCart } from "../components/icons";
import {
  fetchMarketplaceRecommendationWhy,
  listMarketplaceProducts,
  listMarketplaceRecommendations,
  sendMarketplaceClientEvents,
} from "../api/marketplace";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { EmptyState } from "../components/EmptyState";
import { AppErrorState, AppForbiddenState } from "../components/states";
import type {
  MarketplaceProductSummary,
  MarketplaceRecommendationItem,
  MarketplaceRecommendationWhyResponse,
} from "../types/marketplace";
import { canOrder } from "../utils/marketplacePermissions";
import { useI18n } from "../i18n";

interface CatalogErrorState {
  message: string;
  status?: number;
  correlationId?: string | null;
}

export function MarketplaceCatalogPage() {
  const { user } = useAuth();
  const location = useLocation();
  const { t } = useI18n();
  const [items, setItems] = useState<MarketplaceProductSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<CatalogErrorState | null>(null);
  const [recommendations, setRecommendations] = useState<MarketplaceRecommendationItem[]>([]);
  const [isRecommendationsLoading, setIsRecommendationsLoading] = useState(false);
  const [whyPayload, setWhyPayload] = useState<MarketplaceRecommendationWhyResponse | null>(null);
  const [isWhyLoading, setIsWhyLoading] = useState(false);
  const [isWhyOpen, setIsWhyOpen] = useState(false);
  const [whyError, setWhyError] = useState<string | null>(null);
  const [filters, setFilters] = useState({
    q: "",
    category: "",
    type: "",
  });
  const [showAllCategories, setShowAllCategories] = useState(false);
  const canOrderProduct = canOrder(user);
  const initialSearchRef = useRef(true);
  const searchDebounceRef = useRef<number | null>(null);
  const hasActiveFilters = Boolean(filters.q || filters.category || filters.type);

  const categories = useMemo(
    () =>
      Array.from(new Set(items.map((item) => item.category).filter((value): value is string => Boolean(value))))
        .sort((a, b) => a.localeCompare(b)),
    [items],
  );

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

  const loadRecommendations = () => {
    if (!user) return;
    setIsRecommendationsLoading(true);
    listMarketplaceRecommendations(user, 12)
      .then((resp) => setRecommendations(resp.items ?? []))
      .catch(() => setRecommendations([]))
      .finally(() => setIsRecommendationsLoading(false));
  };

  useEffect(() => {
    loadCatalog();
  }, [user, filters]);

  useEffect(() => {
    loadRecommendations();
  }, [user]);

  useEffect(() => {
    if (!user) return;
    if (initialSearchRef.current) {
      initialSearchRef.current = false;
      return;
    }
    if (searchDebounceRef.current) {
      window.clearTimeout(searchDebounceRef.current);
    }
    searchDebounceRef.current = window.setTimeout(() => {
      void sendMarketplaceClientEvents(user, [
        {
          event_type: "marketplace.search_performed",
          entity_type: "NONE",
          source: "client_portal",
          page: location.pathname,
          payload: {
            q: filters.q || null,
            category: filters.category || null,
            type: filters.type || null,
          },
        },
      ]).catch(() => undefined);
    }, 700);
    return () => {
      if (searchDebounceRef.current) {
        window.clearTimeout(searchDebounceRef.current);
      }
    };
  }, [
    filters.category,
    filters.q,
    filters.type,
    location.pathname,
    user,
  ]);

  const handleFilterChange = (evt: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = evt.target;
    setFilters((prev) => ({ ...prev, [name]: value }));
  };

  const handleCategoryClick = (category: string) => {
    setFilters((prev) => ({ ...prev, category }));
  };

  const handleWhyClick = (item: MarketplaceRecommendationItem) => {
    if (!user) return;
    setIsWhyOpen(true);
    setIsWhyLoading(true);
    setWhyPayload(null);
    setWhyError(null);
    fetchMarketplaceRecommendationWhy(user, item.offer_id)
      .then((resp) => setWhyPayload(resp))
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setWhyError(err.message);
          return;
        }
        setWhyError(err instanceof Error ? err.message : t("marketplaceCatalog.recommendations.whyError"));
      })
      .finally(() => setIsWhyLoading(false));
  };

  const handleWhyClose = () => {
    setIsWhyOpen(false);
    setWhyPayload(null);
    setWhyError(null);
  };

  if (!user) {
    return <AppForbiddenState message={t("marketplaceCatalog.forbidden.clientOnly")} />;
  }

  if (error?.status === 403) {
    return <AppForbiddenState message={t("marketplaceCatalog.forbidden.catalogDenied")} />;
  }

  return (
    <div className="stack">
      {!isRecommendationsLoading && recommendations.length > 0 ? (
        <div className="card">
          <div className="card__header">
            <div>
              <h2>{t("marketplaceCatalog.recommendations.title")}</h2>
              <p className="muted">{t("marketplaceCatalog.recommendations.subtitle")}</p>
            </div>
          </div>
          <div className="grid two">
            {recommendations.map((item) => (
              <div className="card" key={item.offer_id}>
                <div className="stack">
                  <div>
                    <h3>{item.title}</h3>
                    <div className="muted small">{item.reason_hint ?? t("marketplaceCatalog.recommendations.reasonFallback")}</div>
                  </div>
                  <div className="badge-row">
                    <span className="neft-chip neft-chip-muted">
                      {item.category ?? t("marketplaceCatalog.card.categoryFallback")}
                    </span>
                    <span className="neft-chip neft-chip-info">
                      {item.subject_type === "SERVICE"
                        ? t("marketplaceCatalog.types.service")
                        : t("marketplaceCatalog.types.product")}
                    </span>
                  </div>
                  {item.preview?.short ? <div className="muted">{item.preview.short}</div> : null}
                  <div className="actions">
                    <button type="button" className="ghost" onClick={() => handleWhyClick(item)}>
                      {t("marketplaceCatalog.recommendations.whyAction")}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

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

      {isWhyOpen ? (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-card">
            <div className="card__header">
              <div>
                <h3>{t("marketplaceCatalog.recommendations.whyTitle")}</h3>
                <p className="muted">{t("marketplaceCatalog.recommendations.whySubtitle")}</p>
              </div>
              <button type="button" className="ghost" onClick={handleWhyClose}>
                {t("actions.close")}
              </button>
            </div>
            <div className="stack">
              {isWhyLoading ? (
                <div className="skeleton-stack">
                  <div className="skeleton-line" />
                  <div className="skeleton-line" />
                </div>
              ) : null}
              {whyError ? <div className="muted">{whyError}</div> : null}
              {!isWhyLoading && !whyError ? (
                <ul>
                  {(whyPayload?.reasons ?? []).map((reason) => (
                    <li key={reason.code}>{reason.label}</li>
                  ))}
                </ul>
              ) : null}
              {!isWhyLoading && !whyError && (whyPayload?.reasons?.length ?? 0) === 0 ? (
                <div className="muted">{t("marketplaceCatalog.recommendations.whyEmpty")}</div>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
