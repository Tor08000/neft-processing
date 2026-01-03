import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getMarketplaceProduct } from "../api/marketplace";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/AuthContext";
import { AppEmptyState, AppErrorState, AppForbiddenState } from "../components/states";
import type { MarketplaceProductDetails } from "../types/marketplace";
import { useI18n } from "../i18n";
import { canOrder } from "../utils/marketplacePermissions";
import { Toast } from "../components/Toast/Toast";
import { useToast } from "../components/Toast/useToast";

interface ProductErrorState {
  message: string;
  status?: number;
  correlationId?: string | null;
}

const ORDERING_ENABLED = import.meta.env.VITE_MARKETPLACE_ORDERING === "1";

export function MarketplaceProductDetailsPage() {
  const { productId } = useParams<{ productId: string }>();
  const { user } = useAuth();
  const { t } = useI18n();
  const { toast, showToast } = useToast();
  const [product, setProduct] = useState<MarketplaceProductDetails | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<ProductErrorState | null>(null);

  const canOrderProduct = canOrder(user);
  const obligations = useMemo(
    () => product?.sla_summary?.obligations?.slice(0, 5) ?? [],
    [product?.sla_summary?.obligations],
  );

  const loadProduct = () => {
    if (!user || !productId) return;
    setIsLoading(true);
    setError(null);
    getMarketplaceProduct(user, productId)
      .then((resp) => setProduct(resp))
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setError({ message: err.message, status: err.status, correlationId: err.correlationId });
          return;
        }
        setError({ message: err instanceof Error ? err.message : t("marketplaceProduct.errors.loadFailed") });
      })
      .finally(() => setIsLoading(false));
  };

  useEffect(() => {
    loadProduct();
  }, [user, productId]);

  const handleOrderClick = () => {
    if (!ORDERING_ENABLED) {
      showToast({ text: t("marketplaceProduct.orderingSoon"), kind: "info" });
      return;
    }
    showToast({ text: t("marketplaceProduct.orderingEnabled"), kind: "success" });
  };

  if (!user) {
    return <AppForbiddenState message={t("marketplaceProduct.forbidden.clientOnly")} />;
  }

  if (error?.status === 403) {
    return <AppForbiddenState message={t("marketplaceProduct.forbidden.productDenied")} />;
  }

  if (error?.status === 404) {
    return (
      <AppEmptyState title={t("marketplaceProduct.notFoundTitle")} description={t("marketplaceProduct.notFoundDescription")} />
    );
  }

  return (
    <div className="stack">
      <div className="card">
        <div className="card__header">
          <div>
            <h2>{t("marketplaceProduct.title")}</h2>
            <p className="muted">{t("marketplaceProduct.subtitle")}</p>
          </div>
          <Link to="/marketplace" className="link-button">
            {t("marketplaceProduct.backToMarketplace")}
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
          <AppErrorState message={error.message} status={error.status} correlationId={error.correlationId} onRetry={loadProduct} />
        ) : null}

        {!isLoading && !error && product ? (
          <div className="stack">
            <div className="stack">
              <div className="stack">
                <div>
                  <h3>{product.title}</h3>
                  <div className="muted small">
                    {product.partner?.company_name ?? t("marketplaceProduct.partnerFallback")}
                  </div>
                </div>
                <div className="badge-row">
                  <span className="badge badge-muted">
                    {product.category ?? t("marketplaceProduct.categoryFallback")}
                  </span>
                  <span className="badge badge-info">
                    {product.type === "SERVICE" ? t("marketplaceCatalog.types.service") : t("marketplaceCatalog.types.product")}
                  </span>
                  {product.partner?.verified ? (
                    <span className="badge badge-success">{t("marketplaceProduct.verifiedBadge")}</span>
                  ) : null}
                </div>
              </div>

              <div className="card muted-card">
                <div className="muted small">{t("marketplaceProduct.priceLabel")}</div>
                <div className="section-title">
                  <h3>{product.price_summary ?? t("marketplaceProduct.priceFallback")}</h3>
                  {canOrderProduct ? (
                    <button type="button" className="primary" onClick={handleOrderClick}>
                      {t("marketplaceProduct.order")}
                    </button>
                  ) : null}
                </div>
              </div>
            </div>

            <div className="stack">
              <div>
                <div className="muted small">{t("marketplaceProduct.descriptionLabel")}</div>
                <div>{product.description ?? t("marketplaceProduct.descriptionFallback")}</div>
              </div>
            </div>

            <div className="card muted-card">
              <div className="section-title">
                <h3>{t("marketplaceProduct.sla.title")}</h3>
              </div>
              {obligations.length ? (
                <ul className="stack">
                  {obligations.map((obligation, index) => (
                    <li key={`${obligation.metric}-${index}`}>
                      <strong>{obligation.metric}</strong>{" "}
                      <span className="muted">
                        {t("marketplaceProduct.sla.threshold", {
                          threshold: obligation.threshold,
                          comparison: obligation.comparison ?? "",
                          window: obligation.window ?? t("marketplaceProduct.sla.windowDefault"),
                        })}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="muted">{t("marketplaceProduct.sla.fallback")}</div>
              )}
              {product.sla_summary?.penalties ? (
                <div className="muted small">{t("marketplaceProduct.sla.penalties", { penalties: product.sla_summary.penalties })}</div>
              ) : null}
            </div>

            <div className="muted small">{t("marketplaceProduct.auditNote")}</div>
          </div>
        ) : null}
      </div>

      {!isLoading && !error && !product ? (
        <AppEmptyState title={t("marketplaceProduct.notFoundTitle")} description={t("marketplaceProduct.notFoundDescription")} />
      ) : null}

      <Toast toast={toast} />
    </div>
  );
}
